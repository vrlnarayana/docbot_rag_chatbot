# DocBot

A local chatbot over your PDFs, images and text files. Ask a question in plain English; every answer cites the document and page it came from, and DocBot says so when the documents do not contain the answer.

- **Runs on your laptop:** FastAPI + SQLite + Streamlit, local OCR and embeddings. No Docker, no database server.
- **Answers:** quoted from the documents by default (no LLM). Optionally written by a local LLM (Ollama) or, with your own API key, by OpenAI or Claude.
- **Built with Spec-Driven Development:** the [constitution](.specify/memory/constitution.md), [spec](specs/001-docbot-rag-chatbot/spec.md), [plan](specs/001-docbot-rag-chatbot/plan.md), [tasks](specs/001-docbot-rag-chatbot/tasks.md) and [traceability](specs/001-docbot-rag-chatbot/traceability.md) are in `specs/`.

## Quick start (about 10 minutes)

You need **Python 3.11, 3.12 or 3.13** (`python3 --version`; on macOS you may need `python3.12`) and Git.

```bash
git clone <this repository> docbot && cd docbot
python3.12 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Start the API in one terminal and the UI in a second one (activate `.venv` in both):

```bash
uvicorn app.api.main:app --port 8000     # first start downloads the ~70 MB embedding model
streamlit run ui/Home.py                 # opens http://localhost:8501
```

In the browser:

1. Open **Documents** and click **Generate & load sample documents**. Eight fictional "Demo Motors" files are created and indexed, including a scanned certificate and two images that are read with OCR.
2. Open **Chat** and ask *"What is the minimum thickness of the front brake disc?"* The answer quotes the table row and cites `DM-STD-BRK-001…pdf · p. 2`. Expand the citation to see the passage.
3. Ask *"What is the top speed of the Velo 125?"* DocBot answers *"I couldn't find this in the uploaded documents."*, because no document says.
4. Open **Evaluate** and click **Run evaluation** to score all 12 golden questions.

You can also upload your own PDF, PNG, JPG, TXT or MD files on the Documents page (PDFs up to 1 MB, other files up to 20 MB). The API is documented at http://localhost:8000/docs.

## Configuration

Copy `.env.example` to `.env` and restart the API after a change. The most useful settings:

| Setting | Default | What it does |
|---|---|---|
| `DOCBOT_RETRIEVER` | `vector` | `keyword` uses BM25 and needs no model download |
| `DOCBOT_GENERATOR` | `extractive` | `ollama` (local LLM), `openai` or `anthropic` (cloud, your own key) |
| `DOCBOT_OPENAI_API_KEY` / `DOCBOT_ANTHROPIC_API_KEY` | — | Required for the cloud generators; `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` also work |
| `DOCBOT_MIN_COVERAGE` | `0.55` | Raise it if out-of-scope questions get answered |
| `DOCBOT_MAX_PDF_MB` / `DOCBOT_MAX_UPLOAD_MB` | `1` / `20` | Upload limits |

With `openai` or `anthropic`, each question and the passages retrieved for it are sent to that provider; the Status page and the chat sidebar say so. Every other setting keeps your documents on this machine. An unknown value (for example `DOCBOT_GENERATOR=azure_openai`) stops the API at startup with a message listing the valid options.

## Development

```bash
pytest && ruff check . && mypy --strict app/core      # the quality gate; must pass before a task is done
pytest tests/unit/test_chunking.py                    # one file
pytest -k fr_012                                      # every test for one requirement
python scripts/generate_samples.py                    # regenerate sample_data/ and eval/golden.yaml
python scripts/reset_demo.py                          # delete data/ (asks you to type RESET)
```

Tests never call the network or an LLM: they use the keyword retriever, a fake generator and stand-in API clients. `app/core` holds the pure business logic; everything that touches files, the database, OCR, models or HTTP is an adapter in `app/adapters` or `app/api`.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `uvicorn` exits with "invalid configuration" | Read the message: it names the setting and the valid values |
| The embedding model will not download (proxy, offline) | Set `DOCBOT_RETRIEVER=keyword`; the Status page also shows when the API fell back to it |
| `ImportError: Library not loaded … cv2 … .dylib` | Antivirus software can quarantine OpenCV's bundled libraries. Exclude `.venv/` (and your pip or uv cache), then reinstall: `pip install --force-reinstall --no-cache-dir opencv-python` |
| The UI shows "DocBot API not reachable" | Start the API, or set `DOCBOT_API_URL` in `.env` |

---

# Trainer guide

A ready-to-build specification for **DocBot**. You give the spec pack to Claude Code, and it builds the app from the spec while learners watch the Spec-Driven Development workflow: constitution → spec → plan → tasks → implement → verify.

- **Stack:** FastAPI · SQLite · Streamlit · local OCR and embeddings · optional Ollama
- **Cloud:** none by default. OpenAI and Claude are optional (constitution 1.1.0); Azure arrives later as SPEC-002, through new adapters only.
- **Data:** a synthetic corpus ("Demo Motors", model "Velo 125") that the app generates itself

## What's in the pack

| File | Purpose | Who writes it in real SDD |
|---|---|---|
| `.specify/memory/constitution.md` | Project rules: stack, architecture, testing, traceability | Team, once |
| `specs/001-docbot-rag-chatbot/spec.md` | **What and why**: 5 user stories, 35 EARS requirements, success criteria, sample corpus, golden questions | Product / domain owner |
| `specs/001-docbot-rag-chatbot/plan.md` | **How**: architecture, data model, API contract, algorithms, test plan | Agent, reviewed by an engineer |
| `CLAUDE.md` | Claude Code's project memory: reading order, way of working, guardrails | Team |
| `tasks.md`, `traceability.md` | Generated by the agent; that is part of the demo. In this repository they are filled in. | Agent |

## Prerequisites
- Python 3.11–3.13 and Git
- Claude Code, signed in
- About 1.5 GB free disk (OCR runtime and embedding model)
- Internet for `pip install` and the one-time embedding-model download (~70 MB)
- Optional: [Ollama](https://ollama.com) with `ollama pull llama3.2:3b`, to show a real LLM writing the answers

## Path A — plain Claude Code (simplest)

```bash
mkdir docbot && cd docbot
# copy the contents of this pack here, then:
git init && git add . && git commit -m "SPEC-001: constitution, spec, plan"
claude
```

Kick-off prompt:

> Read CLAUDE.md, then the constitution, spec and plan for SPEC-001. First generate `specs/001-docbot-rag-chatbot/tasks.md` and stop so I can review it. Do not write code yet.

After reviewing the tasks with the class:

> Implement Phase 1 and Phase 2 from tasks.md, one task at a time, following CLAUDE.md. Stop after Phase 2 and summarise.

Then continue one user story at a time: *"Implement US-1"*, *"Implement US-2"*, and so on.

## Path B — GitHub Spec Kit (shows the full toolchain)

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
mkdir docbot && cd docbot
specify init --here --ai claude
# then copy this pack in, overwriting .specify/memory/constitution.md
claude
```

Inside Claude Code:

| Step | Command | What to show the class |
|---|---|---|
| 1 | *(skip)* `/speckit.constitution` | The constitution is already written; walk through Articles I and III |
| 2 | *(skip)* `/speckit.specify` | The spec is already written; walk through US-2 and FR-012 |
| 3 | `/speckit.clarify` | Optional: let it look for gaps; compare with §9 Clarifications |
| 4 | `/speckit.plan` | **Delete `plan.md` first** so the agent writes its own; compare it with the reference copy afterwards |
| 5 | `/speckit.tasks` | Review the generated tasks; check that each has FR tags |
| 6 | `/speckit.analyze` | Consistency check across spec, plan and tasks |
| 7 | `/speckit.implement` | Build, one phase at a time |

Command names vary between Spec Kit versions; older releases use `/specify`, `/plan` and `/tasks`.

## Suggested demo flow (about 2.5 hours, including build time)

| Time | Activity | Teaching point |
|---|---|---|
| 0:00 | Open `spec.md`; read US-2 and its acceptance scenarios aloud | A spec is readable by non-programmers |
| 0:10 | Show FR-012 (refusal) and §8 golden set | Requirements become tests before any code exists |
| 0:15 | Generate `tasks.md`; review FR tags | Traceability starts at planning |
| 0:25 | Build Setup + Foundation | The harness goes up before the features |
| 0:50 | Build US-1; upload the brake standard; show its chunks | Parsing and chunking decide quality |
| 1:15 | Build US-2; ask the table, scanned-PDF and image questions | Citations; OCR finds facts that keyword search misses |
| 1:35 | Ask *"What is the top speed of the Velo 125?"* | Grounded refusal (FR-012) |
| 1:45 | Build US-3, US-4, US-5 and the UI | |
| 2:15 | Run the evaluation with vector, then keyword retrieval | RAG quality is measured, not eyeballed |
| 2:25 | Open `traceability.md` | Every requirement maps to tasks, code and a passing test |

## Good moments to pause
- **Change the spec live.** Edit FR-007 to 400-character chunks, regenerate the affected task, re-run the evaluation, and discuss the result. This is the "edit the spec, not the code" lesson.
- **Break the contract on purpose.** Set `DOCBOT_GENERATOR=azure_openai` and start the API; FR-052 stops it with a clear message. That is the hook into SPEC-002.
- **Turn on Ollama.** Set `DOCBOT_GENERATOR=ollama`; the same questions now get written answers with the same citations, and the same refusal rules.

## If something goes wrong

| Symptom | Fix |
|---|---|
| The embedding model will not download (proxy) | Set `DOCBOT_RETRIEVER=keyword`; the app works without embeddings |
| The out-of-scope question is answered instead of refused | Raise `DOCBOT_MIN_COVERAGE` or `DOCBOT_MIN_SCORE_VECTOR` and re-run the evaluation |
| OCR misses text in a generated image | Increase the font size in `app/adapters/samples.py` and regenerate the samples |
| The agent drifts from the spec | Point it back: *"Re-read the constitution Article I and the FR ids for this task."* |

## After SPEC-001
SPEC-002 (Azure) swaps adapters, not the core: Blob Storage for the file store, Content Understanding for extraction, AI Search for the retriever, Azure OpenAI for the generator, and Container Apps for hosting. Writing that spec is a good exercise for learners.
