"""Answerability gate (FR-012, plan §7.2 step 4).

Coverage = (IDF weight of question terms found in the retrieved chunks) / (IDF weight of all
question terms). A term that appears in no chunk gets the maximum weight, so "top speed of the
Velo 125" is not answerable just because "Velo 125" is in the corpus.
"""

import math
from collections import Counter

from app.core.text import tokenize


class AnswerabilityGate:
    def __init__(self) -> None:
        self._stats: tuple[int, Counter[str]] = (0, Counter())

    def refresh(self, chunk_texts: list[str]) -> None:
        df: Counter[str] = Counter()
        for text in chunk_texts:
            df.update(set(tokenize(text)))
        self._stats = (len(chunk_texts), df)  # swapped in one assignment

    def weight(self, term: str) -> float:
        n, df = self._stats
        return math.log((n + 1) / (df[term] + 1)) + 1

    def coverage(self, question: str, retrieved_texts: list[str]) -> float:
        terms = set(tokenize(question))
        if not terms:
            return 0.0
        found: set[str] = set()
        for text in retrieved_texts:
            found.update(tokenize(text))
        total = sum(self.weight(t) for t in terms)
        return sum(self.weight(t) for t in terms & found) / total
