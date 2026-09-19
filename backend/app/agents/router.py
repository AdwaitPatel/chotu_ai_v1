"""
Agent Router — the box between the Intent Engine and Business Tools in
the architecture diagram. Dispatches a ParsedIntent to whichever
specialized agent owns that intent.

Only the Cart Agent is fully implemented; other agents are stubbed so
the router's shape (and the /api/voice/query contract) is stable and
new agents can be dropped in without touching this file's callers.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cart_agent import AgentResponse, CartAgent
from app.agents.order_agent import OrderAgent
from app.agents.inventory_agent import InventoryAgent
from app.core.redis_client import get_session_memory
from app.intent.schemas import IntentType, ParsedIntent
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.agents.payment_agent import PaymentAgent
from app.core.dependencies import current_merchant
from app.services.analytics_service import AnalyticsService


def _not_implemented(agent_name: str) -> AgentResponse:
    return AgentResponse(
        speech=f"{agent_name} abhi build ho raha hai — jald hi available hoga.",
        data={},
        success=False,
    )


class AgentRouter:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cart_agent = CartAgent(CartService(session))
        self.order_agent = OrderAgent(OrderService(session))
        self.inventory_agent = InventoryAgent(session)

    async def route(self, customer_id: int, intent: ParsedIntent) -> AgentResponse:
        session_state = await get_session_memory(customer_id).get()
        if intent.intent in {IntentType.DAILY_SALES, IntentType.WEEKLY_SALES, IntentType.MONTHLY_SALES, IntentType.TOP_PRODUCTS, IntentType.GROWTH_INSIGHTS}:
            merchant = await current_merchant(self.session)
            if intent.intent == IntentType.GROWTH_INSIGHTS:
                plan = await AnalyticsService(self.session, merchant.id).growth_plan()
                speech = "Sales badhane ke liye yeh kaam kijiye: " + " ".join(plan['growth_actions'])
                return AgentResponse(speech, plan, intent=intent.intent.value)
            period = {IntentType.DAILY_SALES: 'day', IntentType.MONTHLY_SALES: 'month'}.get(intent.intent, 'week')
            report = await AnalyticsService(self.session, merchant.id).report(period)
            return AgentResponse(report['summary'] + ' ' + ' '.join(report['insights'] + report['recommendations']), report, intent=intent.intent.value)
        if session_state.get('pending_payment'):
            return await PaymentAgent(self.session).handle(customer_id, intent, session_state['pending_payment'])

        # A draft must not trap the merchant in its confirmation loop.  Explicit
        # commands start a fresh flow (or cancel the old one) instead of being
        # interpreted as the next answer to a customer-name question.
        if session_state.get("pending_order") and intent.intent == IntentType.CANCEL_ORDER:
            await get_session_memory(customer_id).update(pending_order=None)
            return AgentResponse("Theek hai, adhura bill cancel kar diya.", {}, intent="ORDER_DRAFT")
        if session_state.get("pending_order") and intent.intent == IntentType.RESTOCK_INVENTORY:
            await get_session_memory(customer_id).update(pending_order=None)
            return await self.inventory_agent.restock(intent)
        if session_state.get("pending_order") and intent.intent == IntentType.CREATE_ORDER:
            return await self.order_agent.start(customer_id, intent)
        if session_state.get("pending_order"):
            return await self.order_agent.continue_draft(customer_id, intent)

        if intent.intent == IntentType.CREATE_ORDER:
            return await self.order_agent.start(customer_id, intent)

        if intent.intent == IntentType.RESTOCK_INVENTORY:
            return await self.inventory_agent.restock(intent)

        if intent.intent in CartAgent.SUPPORTED_INTENTS:
            return await self.cart_agent.handle(customer_id, intent)

        if intent.intent in {
            IntentType.REPEAT_ORDER,
            IntentType.CANCEL_ORDER,
        }:
            return _not_implemented("Order Agent")

        if intent.intent in {IntentType.CHECK_PRICE, IntentType.CHECK_STOCK}:
            return _not_implemented("Product/Inventory Agent")

        if intent.intent in {
            IntentType.DAILY_SALES,
            IntentType.WEEKLY_SALES,
            IntentType.MONTHLY_SALES,
            IntentType.TOP_PRODUCTS,
        }:
            return _not_implemented("Analytics Agent")

        if intent.intent == IntentType.GST_REPORT:
            return _not_implemented("GST Agent")

        if intent.intent in {IntentType.GROWTH_INSIGHTS, IntentType.FORECAST_DEMAND}:
            return _not_implemented("Growth Agent")

        return AgentResponse(
            speech="Maaf kijiye, main yeh samajh nahi paaya. Kripya dobara boliye.",
            data={},
            success=False,
        )
