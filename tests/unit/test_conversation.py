import pytest

from app.core.conversation import small_talk_kind, small_talk_reply
from tests.conftest import FakeGenerator
from tests.unit.test_qa_service import FakeRetriever, rc, service


@pytest.mark.parametrize(
    ("message", "kind"),
    [
        ("hi", "greeting"), ("Hello!", "greeting"), ("hey there", "greeting"),
        ("Good morning, DocBot", "greeting"), ("hi, how are you?", "greeting"),
        ("thanks", "thanks"), ("Thank you very much!", "thanks"), ("ok thanks", "thanks"),
        ("bye", "goodbye"), ("See you", "goodbye"),
        ("help", "help"), ("What can you do?", "help"), ("who are you", "help"),
        ("What can I ask you?", "help"),
    ],
)
def test_fr_071_small_talk_is_recognised(message: str, kind: str) -> None:
    assert small_talk_kind(message) == kind


@pytest.mark.parametrize(
    "message",
    ["hi, what is the rear tyre pressure?", "What is the minimum thickness?",
     "thanks, and the rear one?", "Who is the CEO of Demo Motors?", "help me find the torque"],
)
def test_fr_071_real_questions_are_not_small_talk(message: str) -> None:
    assert small_talk_kind(message) is None


def test_fr_071_replies_are_friendly_and_point_to_documents() -> None:
    assert "document" in small_talk_reply("greeting").lower()
    assert "cite" in small_talk_reply("help").lower()
    assert len({small_talk_reply(k) for k in ("greeting", "thanks", "goodbye", "help")}) == 4


async def test_fr_071_small_talk_skips_retrieval_and_generation() -> None:
    retriever, generator = FakeRetriever([rc(0)]), FakeGenerator()
    reply = await service(retriever, generator, chunks=0).ask("Hello!", 4)
    assert reply.small_talk is True
    assert (reply.grounded, reply.citations, reply.generator_used) == (False, [], "none")
    assert retriever.calls == [] and generator.calls == 0
    assert reply.answer == small_talk_reply("greeting")
