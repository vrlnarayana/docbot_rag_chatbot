"""Tokenizer shared by the keyword retriever, the answerability gate and the extractive generator.

Lower-case, split on non-alphanumerics, drop stop-words (including question words) and strip a
trailing 's' (plan §7.2).
"""

import re

_WORD = re.compile(r"[a-z0-9]+")

STOP_WORDS = frozenset(
    """
    a an and are as at be been being but by can could did do does doing for from had has
    in into is it its may might must of on or our shall should so than that the their them
    then there these they this those to under up very was we were will with would you your
    what which who whom whose when where why how many much
    i me my please tell give show find
    """.split()
)


def tokenize(text: str) -> list[str]:
    tokens = []
    for word in _WORD.findall(text.lower()):
        if word in STOP_WORDS:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        tokens.append(word)
    return tokens
