"""Stateful conversational order and bill creation agent."""
import re

from app.agents.cart_agent import AgentResponse
from app.core.redis_client import get_session_memory
from app.intent.schemas import ParsedIntent
from app.services.order_service import (
    OrderInsufficientStockError,
    OrderProductNotFoundError,
    OrderService,
)


class OrderAgent:
    def __init__(self, order_service: OrderService):
        self.order_service = order_service

    async def start(self, customer_id: int, intent: ParsedIntent) -> AgentResponse:
        draft = self._draft_from_intent(intent)
        memory = get_session_memory(customer_id)
        await memory.update(pending_order={"stage": "items", "items": draft})
        if draft:
            return AgentResponse(
                speech=f"Maine {self._item_summary(draft)} note kar liya. Aur items boliye, ya complete hone par 'done' boliye.",
                data={"stage": "items", "items": draft},
                intent="ORDER_DRAFT",
            )
        return AgentResponse(
            speech="Bil ke items aur quantity boliye. Sab items bolne ke baad 'done' boliye.",
            data={"stage": "items", "items": []},
            intent="ORDER_DRAFT",
        )

    async def continue_draft(self, customer_id: int, intent: ParsedIntent) -> AgentResponse:
        memory = get_session_memory(customer_id)
        state = await memory.get()
        draft_state = state.get("pending_order", {})
        stage = draft_state.get("stage")
        items = draft_state.get("items", [])

        if stage == "items":
            new_items = self._draft_from_intent(intent)
            customer_name = self._customer_name_from_finalization(intent.raw_text)
            if customer_name and items:
                await memory.update(
                    pending_order={"stage": "confirm_customer", "items": items, "customer_name": customer_name}
                )
                return AgentResponse(
                    speech=f"Maine customer ka naam '{customer_name}' suna hai. Kya isi naam se bill banana hai? Haan ya nahi boliye.",
                    data={"stage": "confirm_customer", "customer_name": customer_name, "items": items},
                    intent="ORDER_DRAFT",
                )
            if self._is_complete(intent.raw_text):
                if new_items:
                    items = self._merge_items(items, new_items)
                if not items:
                    return AgentResponse("Abhi koi item note nahi hua. Item aur quantity boliye.", {}, False, "ORDER_DRAFT")
                await memory.update(pending_order={"stage": "customer_name", "items": items})
                return AgentResponse(
                    speech="Items complete hain. Bill kiske naam pe banana hai?",
                    data={"stage": "customer_name", "items": items},
                    intent="ORDER_DRAFT",
                )
            if not new_items:
                return AgentResponse("Item aur quantity samajh nahi aayi. Jaise '2 kilo chawal' boliye.", {}, False, "ORDER_DRAFT")
            items = self._merge_items(items, new_items)
            await memory.update(pending_order={"stage": "items", "items": items})
            return AgentResponse(
                speech=f"{self._item_summary(new_items)} note kar liya. Aur item boliye, ya 'done' boliye.",
                data={"stage": "items", "items": items},
                intent="ORDER_DRAFT",
            )

        if stage == "customer_name":
            name = (
                self._customer_name_from_self_intro(intent.raw_text)
                or self._customer_name_from_named_bill_phrase(intent.raw_text)
                or self._clean_customer_name(intent.raw_text)
            )
            if len(name) < 2:
                return AgentResponse("Kripya bill ke liye customer ka naam boliye.", {}, False, "ORDER_DRAFT")
            await memory.update(
                pending_order={"stage": "confirm_customer", "items": items, "customer_name": name}
            )
            return AgentResponse(
                speech=f"Maine customer ka naam '{name}' suna hai. Kya isi naam se bill banana hai? Haan ya nahi boliye.",
                data={"stage": "confirm_customer", "customer_name": name, "items": items},
                intent="ORDER_DRAFT",
            )

        if stage == "confirm_customer":
            name = self._clean_customer_name(draft_state.get("customer_name", ""))
            corrected_name = (
                self._customer_name_from_self_intro(intent.raw_text)
                or self._customer_name_from_named_bill_phrase(intent.raw_text)
            )
            if corrected_name and corrected_name.casefold() != name.casefold():
                await memory.update(
                    pending_order={"stage": "confirm_customer", "items": items, "customer_name": corrected_name}
                )
                return AgentResponse(
                    speech=f"Theek hai, maine customer ka naam '{corrected_name}' suna hai. Kya isi naam se bill banana hai? Haan ya nahi boliye.",
                    data={"stage": "confirm_customer", "customer_name": corrected_name, "items": items},
                    intent="ORDER_DRAFT",
                )
            if self._is_negative(intent.raw_text):
                await memory.update(pending_order={"stage": "customer_name", "items": items})
                return AgentResponse(
                    "Theek hai, customer ka sahi naam boliye.",
                    {"stage": "customer_name", "items": items},
                    intent="ORDER_DRAFT",
                )
            if not self._is_affirmative(intent.raw_text):
                return AgentResponse(
                    f"Kripya confirm kijiye: kya bill '{name}' ke naam se banana hai? Haan ya nahi boliye.",
                    {"stage": "confirm_customer", "customer_name": name, "items": items},
                    False,
                    "ORDER_DRAFT",
                )
            try:
                invoice = await self.order_service.create_invoice(name, items)
                # Persist before clearing the recoverable conversational draft.
                await self.order_service.session.commit()
            except OrderProductNotFoundError as error:
                # Do not leave the session waiting for another "haan" after a
                # failed confirmation.  Remove the unavailable product and go
                # back to item entry so the merchant can immediately replace it.
                missing_product = str(error).casefold()
                remaining_items = [
                    item for item in items
                    if str(item.get("product", "")).casefold() != missing_product
                ]
                await memory.update(pending_order={"stage": "items", "items": remaining_items})
                return AgentResponse(
                    f"{error} catalog mein nahi mila, isliye use bill se hata diya. "
                    "Badle ka item aur quantity boliye, phir 'done' boliye.",
                    {"stage": "items", "items": remaining_items, "missing_product": str(error)},
                    False,
                    "ORDER_DRAFT",
                )
            except OrderInsufficientStockError as error:
                return AgentResponse(str(error), {}, False, "ORDER_DRAFT")
            await memory.update(pending_order=None, last_order_id=invoice.order_id, pending_payment={"order_id": invoice.order_id, "stage": "method"})
            return AgentResponse(
                speech=self._invoice_speech(invoice) + " Payment kaise hoga: cash, online ya udhar?",
                data={
                    "order_id": invoice.order_id,
                    "customer_name": invoice.customer_name,
                    "subtotal": invoice.subtotal,
                    "gst_amount": invoice.gst_amount,
                    "total_amount": invoice.total_amount,
                    "items": [line.__dict__ for line in invoice.lines],
                },
                intent="ORDER_CREATED",
            )

        await memory.update(pending_order=None)
        return AgentResponse("Order session reset ho gaya. 'Bill banao' bolkar dobara shuru kijiye.", {}, False, "ORDER_DRAFT")

    @staticmethod
    def _draft_from_intent(intent: ParsedIntent) -> list[dict]:
        return [
            {"product": item.product, "quantity": item.quantity or 1, "unit": item.unit or "piece"}
            for item in intent.items
            if item.product
        ]

    @staticmethod
    def _merge_items(items: list[dict], additions: list[dict]) -> list[dict]:
        merged = [item.copy() for item in items]
        for addition in additions:
            existing = next((item for item in merged if item["product"] == addition["product"]), None)
            if existing:
                existing["quantity"] += addition["quantity"]
            else:
                merged.append(addition.copy())
        return merged

    @staticmethod
    def _is_complete(text: str) -> bool:
        lowered = text.lower()
        return any(word in lowered for word in ("done", "complete", "finish", "bas", "khatam", "हो गया", "बस", "खत्म", "डन"))

    @staticmethod
    def _is_affirmative(text: str) -> bool:
        if OrderAgent._is_negative(text):
            return False
        return bool(re.search(r"(?:^|[\s,।.!?])(?:yes|haan|ha|confirm|sahi|हाँ|हां|हा|ठीक|बिल्कुल|बिलकुल)(?:$|[\s,।.!?])|बना\s*(?:दे|दो|दीजिए)", text.lower()))

    @staticmethod
    def _is_negative(text: str) -> bool:
        return bool(re.search(r"(?:^|[\s,।.!?])(?:no|nahi|nahin|galat|नहीं|नही|गलत|मत)(?:$|[\s,।.!?])", text.lower()))

    @staticmethod
    def _customer_name_from_finalization(text: str) -> str | None:
        """Read a natural shortcut such as 'Rudra ke naam par kar do'."""
        match = re.search(
            r"^(?P<name>.+?)\s+(?:के|ke)\s+नाम\s+(?:पर|pe)\s+"
            r"(?:कर\s*दो|kar\s*do|karo|बना(?:ओ|ऊं)?|bana(?:o)?)",
            text.strip(),
            re.IGNORECASE,
        )
        if not match:
            return None
        return re.sub(r"^(?:बना|bana|bill|बिल)\s+", "", match.group("name").strip(), flags=re.IGNORECASE)

    @staticmethod
    def _customer_name_from_self_intro(text: str) -> str | None:
        """Extract a correction such as 'Adwait hai mera naam'."""
        intro = re.search(r"(?:कस्टमर\s+का|ग्राहक\s+का|मेरा)\s+नाम\s+(?:है\s+)?(.+?)(?:\s+है(?:\s+भाई)?[।.!?]*$|[।.!?]*$)", text.strip())
        if intro:
            return OrderAgent._clean_customer_name(intro.group(1))
        match = re.search(
            r"^(?P<name>.+?)\s+(?:है\s+मेरा\s+नाम|hai\s+mera\s+naam|mera\s+naam\s+(?:hai|is))",
            text.strip(),
            re.IGNORECASE,
        )
        return match.group("name").strip() if match else None

    @staticmethod
    def _customer_name_from_named_bill_phrase(text: str) -> str | None:
        """Extract a name from phrases such as 'Rudra ke naam par bill bana'."""
        correction = re.search(r"(?:बिल\s+(?:ना\s+)?)?([^\s,।]+)\s+(?:के\s+)?नाम\s+(?:से|पर|पे)", text)
        if correction:
            candidate = OrderAgent._clean_customer_name(correction.group(1))
            if candidate.lower() in {"इसी", "इसके", "उसके", "उसी", "इस", "उस", "isi", "usi", "iske", "uske", "same"}:
                return None
            return candidate
        match = re.search(
            r"(?:^|\b(?:bill|बिल|bana|बना)\s+)(?P<name>.+?)\s+"
            r"(?:के|ke)\s+नाम\s+(?:पर|pe)",
            text.strip(),
            re.IGNORECASE,
        )
        if not match:
            return None
        name = match.group("name").strip()
        return re.sub(r"^(?:बना|bana|bill|बिल)\s+", "", name, flags=re.IGNORECASE)

    @staticmethod
    def _clean_customer_name(text: str) -> str:
        """Remove harmless speech punctuation while preserving the spoken name."""
        return re.sub(r"\s+", " ", text.strip(" .,!?।॥")).strip()

    @staticmethod
    def _item_summary(items: list[dict]) -> str:
        return ", ".join(f"{item['quantity']:g} {item['unit']} {item['product']}" for item in items)

    @staticmethod
    def _invoice_speech(invoice) -> str:
        lines = "; ".join(f"{line.quantity:g} {line.unit} {line.product} - ₹{line.line_total:.0f}" for line in invoice.lines)
        return (
            f"{invoice.customer_name} ke naam bill number {invoice.order_id} ban gaya. "
            f"{lines}. Subtotal ₹{invoice.subtotal:.0f}, GST ₹{invoice.gst_amount:.0f}, total ₹{invoice.total_amount:.0f}."
        )
