from app.adapters.generator_extractive import ExtractiveGenerator
from app.core.answerability import AnswerabilityGate
from app.core.models import Chunk, RetrievedChunk

TABLE = (
    "Brake disc specifications\n"
    "Position | Disc diameter | Minimum thickness\n"
    "Front | 276 mm | 3.5 mm\n"
    "Rear | 220 mm | 4.0 mm"
)
FLUID = "Brake fluid\nUse DOT 4 brake fluid.\nReplace every 2 years or 20,000 km."


def rc(i: int, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(id=f"c{i}", document_id="d", page=1, ordinal=i, source="text", text=text),
        filename="f.pdf",
        score=1.0,
    )


def generator(*texts: str) -> ExtractiveGenerator:
    gate = AnswerabilityGate()
    gate.refresh(list(texts))
    return ExtractiveGenerator(gate)


async def test_fr_013_table_header_and_value_row_come_back_together() -> None:
    gen = generator(TABLE, FLUID)
    answer = await gen.generate(
        "What is the minimum thickness of the front brake disc?", [rc(0, TABLE), rc(1, FLUID)]
    )
    assert "Minimum thickness" in answer.text and "Front | 276 mm | 3.5 mm" in answer.text
    assert answer.text.endswith("[1]")
    assert answer.cited == [1]
    assert answer.grounded is True and answer.generator_used == "extractive"


async def test_fr_013_cites_the_chunk_the_window_came_from() -> None:
    gen = generator(TABLE, FLUID)
    answer = await gen.generate("Which brake fluid should be used?", [rc(0, TABLE), rc(1, FLUID)])
    assert "DOT 4" in answer.text
    assert answer.cited == [2] and answer.text.endswith("[2]")


async def test_ties_go_to_the_higher_ranked_chunk() -> None:
    gen = generator("Tyre pressure 33 psi.", "Tyre pressure 33 psi.")
    answer = await gen.generate("tyre pressure", [rc(0, "Tyre pressure 33 psi."),
                                                  rc(1, "Tyre pressure 33 psi.")])
    assert answer.cited == [1]


async def test_long_lines_are_split_into_sentences() -> None:
    filler = " ".join(f"Clause {i} covers general scope of the document." for i in range(8))
    text = f"{filler} Rear sprocket changes from 42T to 43T. {filler}"
    gen = generator(text)
    answer = await gen.generate("What is the new rear sprocket size?", [rc(0, text)])
    assert "42T to 43T" in answer.text
    assert len(answer.text) < len(text) / 3


async def test_output_is_deterministic() -> None:
    gen = generator(TABLE, FLUID)
    q = "What is the minimum thickness of the front brake disc?"
    first = await gen.generate(q, [rc(0, TABLE), rc(1, FLUID)])
    second = await gen.generate(q, [rc(0, TABLE), rc(1, FLUID)])
    assert first == second
