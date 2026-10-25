"""Answerability gate (FR-012, plan §7.2 step 4).

Coverage = (IDF weight of question terms found in the retrieved chunks) / (IDF weight of all
question terms). A term that appears in no chunk gets the maximum weight, so "top speed of the
Velo 125" is not answerable just because "Velo 125" is in the corpus.

Where it sits in `QAService.ask`:
    retrieve top-k chunks → score gate (best score ≥ MIN_SCORE_<retriever>)
    → THIS GATE (coverage ≥ DOCBOT_MIN_COVERAGE, default 0.55) → generator.
The score gate asks "is anything similar?"; this gate asks "do the passages contain *what the
question is about*?". Retrievers rank by overall similarity, so a question about an unknown
attribute of a known subject (top speed of the Velo 125) still retrieves Velo 125 chunks with a
good score. Weighting each question word by how rare it is in the library catches that case.
"""

import math
from collections import Counter

from app.core.text import tokenize


class AnswerabilityGate:
    """Decides whether retrieved passages cover a question well enough to answer it.

    Holds document-frequency statistics for the whole library, rebuilt by `refresh` whenever
    documents are added or deleted. `coverage` is pure arithmetic over those statistics, so it
    is cheap enough to run on every question.
    """

    def __init__(self) -> None:
        # (number of chunks in the library, how many chunks contain each term).
        # Empty until the first refresh; with no chunks every term gets weight 1.0.
        self._stats: tuple[int, Counter[str]] = (0, Counter())

    def refresh(self, chunk_texts: list[str]) -> None:
        """Recount document frequencies from every chunk in the library.

        Called by `IngestionService.refresh_retriever` at startup, after each upload and after
        each delete, so rare/common judgements always match what is actually indexed.
        """
        df: Counter[str] = Counter()
        for text in chunk_texts:
            # set(): a term counts once per chunk, however often it repeats inside it.
            # tokenize() is shared with BM25 and the extractive generator, so all three agree
            # on what a "term" is (lower-case, stop words removed, trailing "s" stripped).
            df.update(set(tokenize(text)))
        # Build fully, then swap in one assignment: a question answered in another thread
        # mid-refresh sees either the old statistics or the new ones, never a mix.
        self._stats = (len(chunk_texts), df)

    def weight(self, term: str) -> float:
        """How informative a term is: smoothed inverse document frequency.

        weight = ln((N + 1) / (df + 1)) + 1, where N = chunks in the library and df = chunks
        containing the term. With N = 11:
            term in 0 chunks (e.g. "speed")  → ln(12 / 1) + 1 ≈ 3.48   (the maximum)
            term in 5 chunks (e.g. "velo")   → ln(12 / 6) + 1 ≈ 1.69
            term in all 11 chunks            → ln(12 / 12) + 1 = 1.00  (the minimum)
        The +1 inside keeps unseen terms finite; the +1 outside keeps common terms above zero,
        so every question word counts for something.
        """
        n, df = self._stats
        return math.log((n + 1) / (df[term] + 1)) + 1

    def coverage(self, question: str, retrieved_texts: list[str]) -> float:
        """Share of the question's information (0.0–1.0) found in the retrieved passages.

        coverage = sum(weight of question terms present in the passages)
                   / sum(weight of all question terms)

        Worked example, "What is the top speed of the Velo 125?" with Velo 125 chunks retrieved:
            terms: top, speed (in no chunk, 3.48 each), velo, 125 (common, ~1.69 each)
            found: velo, 125              → (1.69 + 1.69) / (3.48 + 3.48 + 1.69 + 1.69) ≈ 0.33
            0.33 < 0.55 → QAService refuses, although the retriever's best score was high.
        Whereas "What is the recommended rear tyre pressure?" finds every term in the owner
        manual chunk → 1.0 → answered.
        """
        # Unique content words only: stop words and question words (what, which, how many…)
        # are already removed by tokenize, so they neither help nor hurt.
        terms = set(tokenize(question))
        if not terms:
            # Nothing left to look for ("What is the?"): treat as unanswerable.
            return 0.0
        # Union of terms across all retrieved passages: the answer may be spread over chunks.
        found: set[str] = set()
        for text in retrieved_texts:
            found.update(tokenize(text))
        # Rare terms dominate both sums, so missing one rare term (the thing actually asked
        # about) pulls coverage down far more than missing a common one.
        total = sum(self.weight(t) for t in terms)
        return sum(self.weight(t) for t in terms & found) / total
