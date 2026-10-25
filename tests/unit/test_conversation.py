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


from app.core.conversation import local_standalone  # noqa: E402
from app.core.models import ChatTurn  # noqa: E402

FRONT_Q = "What is the minimum thickness of the front brake disc?"
HISTORY = [ChatTurn(role="user", content=FRONT_Q),
           ChatTurn(role="assistant", content="Front | 276 mm | 3.5 mm [1]")]


@pytest.mark.parametrize(
    "follow_up",
    ["and the rear one?", "What about the rear?", "how about rear", "Also the rear disc?",
     "Is that the wear limit?", "rear?"],
)
def test_fr_070_local_rule_joins_follow_ups_to_the_previous_question(follow_up: str) -> None:
    assert local_standalone(follow_up, HISTORY) == f"{FRONT_Q} {follow_up}"


def test_fr_070_local_rule_leaves_standalone_questions_alone() -> None:
    assert local_standalone("What brake fluid does the brake standard specify?", HISTORY) is None
    assert local_standalone("and the rear one?", []) is None
    only_assistant = [ChatTurn(role="assistant", content="Hi!")]
    assert local_standalone("and the rear one?", only_assistant) is None


class ScriptedRewriter:
    name = "scripted"

    def __init__(self, result: str | None) -> None:
        self.result = result
        self.calls: list[tuple[str, list[ChatTurn]]] = []

    async def rewrite(self, question: str, history: list[ChatTurn]) -> str | None:
        self.calls.append((question, history))
        return self.result


async def test_fr_070_follow_up_is_rewritten_before_retrieval() -> None:
    retriever = FakeRetriever([rc(0), rc(1)])
    qa = service(retriever, FakeGenerator())
    reply = await qa.ask("what about the fluid?", 4, HISTORY)
    assert retriever.calls[0][0] == f"{FRONT_Q} what about the fluid?"
    assert reply.standalone_question == f"{FRONT_Q} what about the fluid?"
    assert reply.grounded


async def test_fr_070_rewriter_is_preferred_and_falls_back_to_the_local_rule() -> None:
    retriever = FakeRetriever([rc(0), rc(1)])
    qa = service(retriever, FakeGenerator())
    qa.rewriter = ScriptedRewriter("What is the minimum thickness of the rear brake disc?")
    reply = await qa.ask("and the rear one?", 4, HISTORY)
    assert reply.standalone_question == "What is the minimum thickness of the rear brake disc?"

    qa.rewriter = ScriptedRewriter(None)  # the LLM could not rewrite
    reply = await qa.ask("and the rear one?", 4, HISTORY)
    assert reply.standalone_question == f"{FRONT_Q} and the rear one?"


async def test_fr_070_no_history_means_no_rewrite() -> None:
    retriever = FakeRetriever([rc(0)])
    qa = service(retriever, FakeGenerator())
    qa.rewriter = ScriptedRewriter("should not be used")
    reply = await qa.ask(FRONT_Q, 4)
    assert reply.standalone_question is None
    assert retriever.calls[0][0] == FRONT_Q
    assert qa.rewriter.calls == []  # type: ignore[attr-defined]


from app.core.conversation import follow_up_terms  # noqa: E402


def test_fr_070_follow_up_terms_ignore_referring_words() -> None:
    assert follow_up_terms("and the rear one?") == {"rear"}
    assert follow_up_terms("what about the top speed?") == {"top", "speed"}
    assert follow_up_terms("how often do you replace it?") == {"often", "replace"}
    assert follow_up_terms("and?") == set()


async def test_fr_070_follow_up_with_none_of_its_words_in_the_passages_is_refused() -> None:
    from app.core.services import REFUSAL

    gen = FakeGenerator()
    qa = service(FakeRetriever([rc(0), rc(1)]), gen)
    history = [ChatTurn(role="user", content=FRONT_Q)]
    reply = await qa.ask("and who is the CEO?", 4, history)
    assert reply.answer == REFUSAL and reply.citations == [] and gen.calls == 0
    ok = await qa.ask("and the rear one?", 4, history)  # no "rear" in TEXTS either
    assert ok.answer == REFUSAL
    passes = await qa.ask("what about the fluid?", 4, history)  # "fluid" is in TEXTS[1]
    assert passes.grounded
