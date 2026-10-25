"""Conversation helpers (FR-070, FR-071): small talk and turning follow-ups into questions."""

import re
from typing import Literal

from app.core.models import ChatTurn
from app.core.text import tokenize

SmallTalk = Literal["greeting", "thanks", "goodbye", "help"]

_PHRASES: dict[SmallTalk, set[str]] = {
    "greeting": {
        "hi",
        "hello",
        "hey",
        "hiya",
        "howdy",
        "greetings",
        "hi there",
        "hello there",
        "hey there",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
        "hi how are you",
        "hello how are you",
        "hey how are you",
    },
    "thanks": {
        "thanks",
        "thank you",
        "thanks a lot",
        "thank you very much",
        "thanks so much",
        "thx",
        "ty",
        "cheers",
        "ok thanks",
        "okay thanks",
        "great thanks",
        "perfect thanks",
        "awesome thanks",
        "much appreciated",
        "thank you so much",
    },
    "goodbye": {"bye", "goodbye", "bye bye", "see you", "see ya", "cya", "good night"},
    "help": {
        "help",
        "what can you do",
        "who are you",
        "what are you",
        "how do you work",
        "how can you help",
        "how can you help me",
        "what do you do",
        "what is docbot",
        "what can i ask",
        "what can i ask you",
    },
}

_REPLIES: dict[SmallTalk, str] = {
    "greeting": (
        "Hi! I'm DocBot. Ask me anything about the documents in your library, and I'll answer "
        "with the file and page each fact comes from."
    ),
    "thanks": "You're welcome! Ask me anything else about your documents.",
    "goodbye": "Goodbye! Your documents will be here when you come back.",
    "help": (
        "I answer questions about the documents in your library: PDFs (including scans), "
        "images and text files. Every answer cites the file and page it came from, and if the "
        "documents don't say, I tell you instead of guessing. You can ask follow-up questions "
        'too. Try "What is the minimum thickness of the front brake disc?" after loading the '
        "sample set."
    ),
}


def _normalise(message: str) -> str:
    words = re.sub(r"[^a-z0-9' ]+", " ", message.lower()).split()
    if words and words[-1] == "docbot":  # "hi docbot", "thanks, DocBot!"
        words = words[:-1]
    return " ".join(words)


def small_talk_kind(message: str) -> SmallTalk | None:
    """The kind of small talk when the whole message is small talk, otherwise None."""
    text = _normalise(message)
    for kind, phrases in _PHRASES.items():
        if text in phrases:
            return kind
    return None


def small_talk_reply(kind: SmallTalk) -> str:
    return _REPLIES[kind]


_FOLLOW_UP_STARTS = ("and", "what about", "how about", "also")
_REFERRING_WORDS = {
    "it",
    "its",
    "that",
    "this",
    "these",
    "those",
    "they",
    "them",
    "their",
    "one",
    "ones",
}
_MIN_CONTENT_WORDS = 3


def looks_like_follow_up(question: str) -> bool:
    words = re.sub(r"[^a-z0-9' ]+", " ", question.lower()).split()
    text = " ".join(words)
    if any(text == start or text.startswith(start + " ") for start in _FOLLOW_UP_STARTS):
        return True
    if _REFERRING_WORDS & set(words):
        return True
    return len(tokenize(question)) < _MIN_CONTENT_WORDS


def local_standalone(question: str, history: list[ChatTurn]) -> str | None:
    """FR-070 local rule: join a follow-up to the previous user question; None if not needed."""
    previous = next((t.content for t in reversed(history) if t.role == "user"), None)
    if previous is None or not looks_like_follow_up(question):
        return None
    return f"{previous} {question}"


_FOLLOW_UP_FILLER = {"about", "also", "and"}


def follow_up_terms(question: str) -> set[str]:
    """The follow-up's own content words, without referring words such as "it" or "one"."""
    return set(tokenize(question)) - _REFERRING_WORDS - _FOLLOW_UP_FILLER
