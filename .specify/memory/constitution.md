# DocBot Constitution

These rules apply to every spec, plan, task and line of code in this repository. If a plan or task conflicts with them, the constitution wins. Change it only by an explicit, versioned amendment at the bottom of this file.

**Version** 1.3.0 · **Ratified** 2026-10-25 · **Last amended** 2026-10-25

---

## Article I — The spec is the source of truth
1. Code exists to satisfy `specs/<id>/spec.md`. When behaviour and spec disagree, fix the code, or amend the spec first and then the code.
2. Every functional requirement (FR-xxx) has at least one automated test, named `test_fr_xxx_<what_it_checks>`.
3. Every task in `tasks.md` names the requirement(s) it implements, e.g. `T014 [FR-012]`.
4. Commit messages start with the task id: `T014: refuse below score threshold`.
5. `specs/<id>/traceability.md` maps every FR to its tasks, source files and tests. It is updated whenever a task is completed. A requirement with no test is a gap and blocks "done".
6. Do not guess. Anything the spec leaves open is marked `[NEEDS CLARIFICATION]` and raised before it is built.

## Article II — Technology stack
| Concern | Choice |
|---|---|
| Language | Python 3.11–3.13, full type hints |
| API | FastAPI + Uvicorn |
| Models / validation | Pydantic v2; strict mode for anything coming from an LLM, a file or a request |
| Settings | `pydantic-settings`, `.env` file |
| Database | SQLite through SQLAlchemy 2.x async + `aiosqlite` |
| PDF text | `pypdf` |
| PDF page rendering (for OCR) | `pypdfium2` |
| OCR | `rapidocr-onnxruntime` (models ship inside the package; works offline) |
| Embeddings | `fastembed` with `BAAI/bge-small-en-v1.5` (ONNX; no PyTorch) |
| Keyword search | `rank-bm25` |
| Local LLM (optional) | Ollama over its HTTP API, called with `httpx` |
| Cloud LLMs (optional, opt-in) | `openai` SDK for OpenAI, `anthropic` SDK for Claude; each used only when selected and given the user's own API key |
| Cloud embeddings (optional, opt-in) | `openai` SDK (OpenAI embeddings API), only when selected and given the user's own API key |
| Retries | `tenacity` |
| Sample documents | `reportlab` (PDF), `Pillow` (images and the scanned PDF) |
| UI | Streamlit, calling the API with `httpx` |
| Tests / quality | `pytest`, `pytest-asyncio`, `ruff`, `mypy --strict` on `app/core` |

Do not add a dependency outside this table without amending the constitution. No Docker, no database server, no vector-database server.

## Article III — Architecture: the core stays pure
Follow a ports-and-adapters layout. Dependencies point inward.

```
app/core/       pure Python: models, ports (Protocols), services. No FastAPI, no SQL, no SDKs, no file I/O.
app/adapters/   implementations of the ports: SQLite repository, extractors, OCR, retrievers, generators.
app/api/        FastAPI routes and dependency wiring. FastAPI is an adapter too.
ui/             Streamlit app. Talks only to the API over HTTP.
```

The ten-point harness is mandatory:
1. Every function boundary has type hints.
2. Every LLM output is parsed into a Pydantic v2 **strict** model (`extra="forbid"`) before use.
3. All I/O in request paths is async. CPU-heavy work (OCR, embedding, PDF rendering) runs in a worker thread (`anyio.to_thread.run_sync`), never inline in the event loop.
4. Every LLM call goes through one typed client wrapper with a timeout, retries with exponential backoff and jitter on transient errors only, and a fallback.
5. Each provider (generator, retriever, extractor, storage) sits behind a port the core owns. The adapter is chosen once, at startup.
6. Any argument coming from a model is validated before it is used. For example, citation numbers must refer to chunks that were actually supplied.
7. Destructive actions are bounded: delete exactly one document by id; no bulk delete over the API; the UI confirms before deleting.
8. Every endpoint declares a request model (where it takes a body) and a `response_model`. Never return raw dicts or ORM objects.
9. Tests assert contracts, not exact wording. Unit tests never call a real LLM or the network.
10. `app/core` imports nothing from `fastapi`, `sqlalchemy`, `sqlite3`, `httpx`, `fastembed`, `rapidocr_onnxruntime`, `pypdf` or `pypdfium2`.

## Article IV — Local-first and data safety
1. No cloud services by default. The only network calls allowed at runtime are to Ollama on `localhost` (optional), the one-time embedding-model download, the API of a cloud generator (OpenAI or Anthropic), and the OpenAI embeddings API, each **only** when the user explicitly selects it and supplies their own API key. A cloud generator receives only the question, the retrieved passages and, for follow-up questions, the recent conversation turns the UI sends. The OpenAI embedder receives the text of every indexed chunk and every question. API keys are never logged or returned by the API.
2. Sample data is synthetic: company "Demo Motors", model "Velo 125". No real company names, people or documents.
3. Uploaded files are stored under generated names inside the configured storage folder. User-supplied file names are never used as paths.
4. API responses never include raw prompts, absolute file paths or stack traces.

## Article V — Testing discipline
1. Write or update the test for a requirement in the same task that implements it.
2. Tests use a temporary database and storage folder, the **keyword** retriever and a **fake** generator, so they are fast and deterministic and need no model downloads.
3. One end-to-end test ingests the generated sample corpus and asserts SC-003, SC-004 and SC-005.
4. `pytest`, `ruff check` and `mypy --strict app/core` must all pass before a task is marked done.

## Article VI — Simplicity
1. Build only what the spec asks for. Note good ideas in `specs/<id>/ideas.md`; do not build them.
2. Prefer the standard library and the stack above over new abstractions.
3. Two processes to run the app: the API and the UI. Ollama is optional and separate.

## Article VII — Developer experience
1. The README lets a newcomer go from clone to a cited answer in under 10 minutes.
2. Errors tell the user what to do next, e.g. "Ollama not reachable at http://localhost:11434 — start it with `ollama serve` or set DOCBOT_GENERATOR=extractive".
3. Logs are structured, one line per request, with a request id. Document text is not written to logs.

---

## Amendments

### 1.3.0 — 2026-10-25 — Conversational chat
- **Why:** The user wants follow-up questions, small talk and conversational answers.
- **Article IV.1:** a cloud generator may also receive the recent conversation turns (at most 6) to rewrite a follow-up into a standalone question. The server stores no conversations; the UI sends the turns with each question.

### 1.2.0 — 2026-10-25 — Optional OpenAI embeddings
- **Why:** The user wants OpenAI's `text-embedding-3-small` for retrieval instead of the local model.
- **Article II:** the `openai` SDK may also be used for embeddings.
- **Article IV.1:** with the OpenAI embedder selected, the full text of every indexed chunk is sent to OpenAI (not only retrieved passages). The default embedder stays local, and the status page and UI say when it is not.

### 1.1.0 — 2026-10-25 — Optional cloud generators
- **Why:** Users who have an OpenAI or Anthropic API key want better-written answers than the extractive generator gives, without installing Ollama.
- **Article II:** adds the `openai` and `anthropic` SDKs, for the optional cloud generators only.
- **Article IV.1:** a cloud generator may be called when the user selects it and supplies their own key. The default configuration stays fully local.
- **Unchanged:** Article III (the core stays pure; the cloud generators are adapters behind the `Generator` port, with strict parsing, retries, timeouts and the extractive fallback), and Article IV.4 (no prompts, paths or keys in API responses). Azure remains SPEC-002.
