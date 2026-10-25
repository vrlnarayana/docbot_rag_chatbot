"""Extractive generator (default, no LLM): quote the best-matching lines with a citation.

Plan §7.4: score every window of up to 3 consecutive lines by IDF-weighted overlap with the
question; ties go to the higher-ranked chunk, then the earlier window. A window keeps a table
header and its value row together.
"""

import re

from app.core.answerability import AnswerabilityGate
from app.core.models import GeneratedAnswer, RetrievedChunk
from app.core.text import tokenize

WINDOW = 3
LONG_LINE = 200
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def _lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in (raw.strip() for raw in text.splitlines()):
        if not line:
            continue
        lines.extend(_SENTENCE_END.split(line) if len(line) > LONG_LINE else [line])
    return lines


class ExtractiveGenerator:
    name = "extractive"

    def __init__(self, gate: AnswerabilityGate) -> None:
        self._gate = gate

    def _score(self, terms: set[str], lines: list[str]) -> float:
        found = set(tokenize(" ".join(lines)))
        return sum(self._gate.weight(t) for t in terms & found)

    async def generate(self, question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
        terms = set(tokenize(question))
        best: tuple[float, int, list[str]] | None = None
        for n, retrieved in enumerate(chunks, start=1):
            lines = _lines(retrieved.chunk.text)
            for start in range(max(len(lines), 1)):
                window = lines[start : start + WINDOW]
                score = self._score(terms, window)
                if best is None or score > best[0]:  # strict: ties keep the earlier window
                    best = (score, n, window)
        if best is None:
            return GeneratedAnswer(text="", cited=[], grounded=False, generator_used=self.name)
        _score, n, window = best
        while len(window) > 1 and not set(tokenize(window[0])) & terms:
            window = window[1:]  # drop leading lines that say nothing about the question
        quote = "\n".join(window)
        return GeneratedAnswer(
            text=f"{quote} [{n}]",
            cited=[n],
            grounded=True,
            generator_used=self.name,
        )
