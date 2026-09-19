"""Catalog matching is injectable; unmatched names remain available for clarification."""
import re
from collections.abc import Sequence

from rapidfuzz import fuzz, process

from app.intent.rule_based_parser import PRODUCT_ALIASES, _normalize_text


class CatalogResolver:
    def __init__(self, catalog: Sequence[str], threshold: float = 80):
        self.catalog = tuple(catalog)
        self.threshold = threshold
        self.normalized = [self.normalize(name) for name in self.catalog]

    @staticmethod
    def normalize(name: str) -> str:
        words = re.findall(r"\w+", _normalize_text(name))
        return " ".join(PRODUCT_ALIASES.get(word, word) for word in words)

    def resolve(self, product: str | None) -> str | None:
        if not product or not self.catalog:
            return product
        match = process.extractOne(self.normalize(product), self.normalized,
                                   scorer=fuzz.ratio, score_cutoff=self.threshold)
        if match is None:
            return product
        # Ambiguous equal matches must not pick an arbitrary SKU.
        if sum(fuzz.ratio(self.normalize(product), name) == match[1]
               for name in self.normalized) > 1:
            return product
        return self.catalog[match[2]]
