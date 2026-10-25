# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# DocBot — project memory for Claude Code

DocBot is a local RAG chatbot over PDFs, images and text files (FastAPI + SQLite + Streamlit). It is built live in a training session to demonstrate **Spec-Driven Development**, so how you work matters as much as what you build.

The repository starts as a spec pack only (constitution, spec, plan). All application code is generated from it, task by task.

## Read these first, in this order
1. `.specify/memory/constitution.md` — the rules. They override everything else.
2. `specs/001-docbot-rag-chatbot/spec.md` — what to build and why (SPEC-001).
3. `specs/001-docbot-rag-chatbot/plan.md` — how to build it (if present; otherwise create it from the spec). §3 is the target file layout, §4 the settings, §7 the algorithms, §12 the phases.

## How to work
- If `specs/001-docbot-rag-chatbot/tasks.md` does not exist, create it from the plan before writing any code. Number tasks `T001…`, tag each with the FR ids it covers (`T014 [FR-012]`), mark tasks that can run in parallel with `[P]`, and group them by user story in priority order.
- Implement **one task at a time**, in order. For each task: write or update its tests, implement, run the quality gate, tick the task in `tasks.md`, update `traceability.md` (FR → tasks, source files, tests), commit as `T0xx: <summary>`.
- Name every requirement test `test_fr_xxx_<what_it_checks>`. A requirement with no test blocks "done".
- After each user story, stop and give a short summary: what works, how to see it in the UI or API, any open issues.
- If the spec is ambiguous, ask or record `[NEEDS CLARIFICATION]` in `tasks.md`. Do not guess, and do not add features the spec does not ask for (put ideas in `specs/001-docbot-rag-chatbot/ideas.md`).
- Do not add a dependency outside the constitution's Article II table without a versioned amendment to the constitution.
- No Azure or cloud code in SPEC-001. If `azure_openai` is configured, startup must fail with a clear message (FR-052).
- If the folder is not yet a git repository, run `git init` and make a first commit of the spec pack before the first task commit.

## Commands
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/generate_samples.py                    # writes sample_data/ and eval/golden.yaml
uvicorn app.api.main:app --reload --port 8000          # API
streamlit run ui/Home.py                               # UI on :8501
pytest && ruff check . && mypy --strict app/core      # quality gate: must pass before a task is done
pytest tests/unit/test_chunking.py                     # one file
pytest -k fr_012                                       # all tests for one requirement
python scripts/reset_demo.py                           # wipes data/ (type RESET to confirm)
```

## Architecture (ports and adapters)
- `app/core/` is pure: Pydantic models, `Protocol` ports, chunking, the answerability gate and the services (`IngestionService`, `QAService`, `EvaluationService`). No file I/O.
- `app/adapters/` implements the ports: SQLite repository, local file store, extractors with OCR, fastembed embedder, vector and BM25 retrievers, extractive and Ollama generators, and the sample-corpus generator.
- `app/api/deps.py` builds every adapter **once at startup** from `app/settings.py` (`DOCBOT_*` env vars and `.env`). An unknown retriever or generator value stops startup.
- `ui/` talks only to the API over HTTP, and only through `ui/api_client.py`.
- **Answering** (`QAService.ask`) refuses in two places: a score gate (`DOCBOT_MIN_SCORE_VECTOR` / `_KEYWORD`), then an IDF-weighted answerability gate (`DOCBOT_MIN_COVERAGE`). Only then does it generate. The model's citation numbers are validated against the chunks that were actually supplied. If Ollama gives invalid output or no valid citations, it falls back to the extractive generator.
- **Ingestion** checks size, then type, then the SHA-256 for duplicates. It extracts in a worker thread: pypdf layout text, with pypdfium2 + OCR for pages under 20 characters. Chunks never cross pages. The file and its DB rows are saved together, and the saved file is removed if the insert fails.
- The defaults (`DOCBOT_RETRIEVER=vector`, `DOCBOT_GENERATOR=extractive`) need no LLM. `DOCBOT_RETRIEVER=keyword` avoids the embedding-model download.

## Testing
- Tests use a temporary DB and storage folder, the keyword retriever and a fake generator (fixtures in `tests/conftest.py`). Mock the Ollama adapter with `httpx.MockTransport`.
- API tests use `httpx.AsyncClient` with `ASGITransport`. They assert the status code, that the body parses into its response model, and that no forbidden fields are present. Assert contracts, not exact wording.
- An architecture test enforces the `app/core` import ban. The end-to-end test (`tests/e2e/test_sample_corpus.py`) runs the 12 golden questions from spec §8 and checks SC-003 to SC-005.

## Guardrails
- `app/core` must not import `fastapi`, `sqlalchemy`, `sqlite3`, `httpx`, `fastembed`, `rapidocr_onnxruntime`, `pypdf` or `pypdfium2`.
- Tests never call the network or a real LLM. Use the keyword retriever and the fake generator.
- Never return raw dicts from endpoints, and never expose file paths, hashes, prompts or stack traces in responses.
- Run OCR, embedding and PDF rendering in a worker thread (`anyio.to_thread.run_sync`), never directly in an async handler.
- Store uploads under generated names. Never use a user-supplied file name as a path.
- Sample data stays synthetic ("Demo Motors", "Velo 125"). Never mention top speed, the CEO or battery warranty in the corpus: they are the refusal test cases.
- Do not write document text to logs.
