import math

from app.core.answerability import AnswerabilityGate

CORPUS = [
    "Demo Motors brake system design standard for the Velo 125.",
    "Front | 276 mm | 3.5 mm minimum thickness. Demo Motors Velo 125.",
    "Velo 125 owner manual. Recommended tyre pressure, solo rider: front 29 psi, rear 33 psi.",
    "Demo Motors engineering change note: Velo 125 rear sprocket changes from 42T to 43T.",
    "Part no. DM-BRK-2210 front brake caliper, 2-piston, supplier code NWC.",
    "Demo Motors handlebar vibration test report, peak 18.2 m/s2.",
]


def gate() -> AnswerabilityGate:
    g = AnswerabilityGate()
    g.refresh(CORPUS)
    return g


def test_fr_012_out_of_corpus_terms_are_not_covered() -> None:
    retrieved = [CORPUS[0], CORPUS[2]]  # both mention "Velo 125"
    assert gate().coverage("What is the top speed of the Velo 125?", retrieved) < 0.55


def test_fr_012_ceo_question_is_not_covered() -> None:
    assert gate().coverage("Who is the CEO of Demo Motors?", [CORPUS[0], CORPUS[3]]) < 0.55


def test_fr_012_unknown_terms_only_gives_zero() -> None:
    assert gate().coverage("What is the warranty period for the battery?", CORPUS[:2]) == 0.0


def test_fr_012_in_corpus_question_passes() -> None:
    g = gate()
    assert g.coverage("What is the recommended rear tyre pressure?", [CORPUS[2]]) == 1.0
    assert g.coverage("How many pistons does the front brake caliper have?", [CORPUS[4]]) >= 0.55


def test_question_with_no_content_words_gives_zero() -> None:
    assert gate().coverage("What is the?", CORPUS) == 0.0


def test_term_in_no_chunk_gets_the_maximum_weight() -> None:
    g = gate()
    assert g.weight("speed") == g.weight("warranty") == math.log(len(CORPUS) + 1) + 1
    assert g.weight("speed") > g.weight("velo")
