# Tasks: DocBot — RAG chatbot over PDFs, images and text files

**Spec:** [spec.md](./spec.md) (SPEC-001) · **Plan:** [plan.md](./plan.md) · **Traceability:** [traceability.md](./traceability.md)

Conventions: `[P]` = can run in parallel with the other `[P]` tasks in the same phase (different files, no dependency). `[FR-xxx]` = requirements the task implements. Each task includes its tests (`test_fr_xxx_<what>`) and ends with the quality gate `pytest && ruff check . && mypy --strict app/core`, a tick here, an update to `traceability.md`, and a commit `T0xx: <summary>`.

---

## Phase 1 — Setup

- [x] T001 [FR-050] `pyproject.toml` (Article II dependencies, `dev` extra, ruff/mypy/pytest config), package layout (`app/core`, `app/adapters`, `app/api/routes`, `ui`, `scripts`, `tests/{unit,api,e2e}`), `.gitignore` (`data/`, `sample_data/`, `.venv/`, `.env`), `.env.example`
- [x] T002 [FR-050, FR-052] `app/settings.py`: `pydantic-settings` with every `DOCBOT_*` variable and default from plan §4; `retriever` / `generator` validated against the implemented options with the exact message from plan §4
- [x] T003 [P] Structured logging: one JSON line per request with request id, method, path, status, duration; no document text (Constitution VII.3)

## Phase 2 — Foundation

- [x] T004 [FR-014, FR-020, FR-021] `app/core/models.py`: domain models (`Document`, `Chunk`, `Page`, `RetrievedChunk`, `GeneratedAnswer`, `GoldenCase`) and API contract models from plan §6 (`DocumentOut`, `ChunkOut`, `CitationOut`, `AskRequest`, `AskResponse`, `UploadResponse`, `DeleteResponse`, `StatusResponse`, `HealthResponse`, `ErrorResponse`, …); `DocumentOut` has no `stored_name`, `sha256` or path
- [x] T005 [P] [NFR-005] `app/core/ports.py` (Protocols: `DocumentRepository`, `FileStore`, `Extractor`, `Embedder`, `Retriever`, `Generator`) and `app/core/errors.py` (`UnsupportedFileType`, `FileTooLarge`, `NoTextExtracted`, `DocumentNotFound`, `ExtractionFailed`)
- [x] T006 [P] Architecture test: `app/core` imports none of the banned modules (Constitution III.10)
- [x] T007 [FR-020, FR-021, FR-022] `app/adapters/db.py`: async SQLAlchemy engine (`aiosqlite`, `PRAGMA foreign_keys=ON`), `documents` / `chunks` tables from plan §5, `SqliteDocumentRepository` (add with chunks in one transaction, get, get by hash, list, chunks in page order, delete one, counts, all chunks)
- [x] T008 [P] [FR-022] `app/adapters/file_store.py`: `LocalFileStore` saving under `<uuid>.<ext>` inside `data/files/`, never using the user file name as a path; delete by stored name (Constitution IV.3)
- [x] T009 [FR-051, FR-052, NFR-006] `app/api/main.py` app factory + lifespan, `app/api/deps.py` (adapters built once from settings), domain-error → `ErrorResponse` handlers (no stack traces), `GET /health`, `GET /status`; `tests/conftest.py` with tmp data dir, keyword retriever and `FakeGenerator`

## Phase 3 — US-1 Upload documents (P1)

- [x] T010 [FR-007] `app/core/chunking.py`: page-aware chunker (≤ 800 chars, 100 overlap, split at blank line → newline → sentence end → space, never cross pages, drop < 20 chars unless only text)
- [x] T011 [P] [FR-006] `TextFileExtractor`: whole file as page 1, UTF-8 then Latin-1
- [x] T012 [P] [FR-005] OCR helper (`rapidocr-onnxruntime`, lines in reading order) and `ImageExtractor` (page 1, `source = ocr`)
- [x] T013 [FR-004] `PdfExtractor`: `pypdf` layout text with column runs collapsed to ` | `; pages under 20 chars rendered with `pypdfium2` at 200 DPI and OCR'd; encrypted/corrupt PDFs → `ExtractionFailed`
- [x] T014 [FR-001, FR-008, FR-009] `IngestionService.ingest` (core): extension check, SHA-256 duplicate check, extraction via the port, no-text rejection, chunking, optional embedding, save file then insert in one transaction, delete file if the insert fails, retriever refresh
- [x] T015 [FR-001, FR-002, FR-003, FR-008, FR-009] `POST /documents`: size limit enforced while streaming (413), type (415 listing supported types), 201 new / 200 duplicate, 422 no text; CPU work in a worker thread
- [x] T038 [FR-003] Per-type size limit: PDFs capped at `DOCBOT_MAX_PDF_MB` (default 1 MB) with 413; other types keep `DOCBOT_MAX_UPLOAD_MB` (added after the FR-003 amendment, 2026-10-25)

## Phase 4 — US-2 Ask a question and get a cited answer (P1)

- [x] T016 [P] [FR-010, FR-011] `Bm25Retriever` (`rank-bm25`, same tokenizer as the answerability gate, refresh on change)
- [x] T017 [P] [FR-011, FR-051] `FastEmbedEmbedder` (worker thread, model cached in `data/models`) and `VectorRetriever` (NumPy cosine over a cached matrix; re-embed chunks whose `embed_model` differs); if the model cannot be loaded at startup, fall back to keyword and report it in `/status` `fallbacks`
- [x] T018 [P] [FR-012] `app/core/answerability.py`: tokenizer + IDF-weighted coverage gate (plan §7.2 step 4)
- [x] T019 [P] [FR-013] `ExtractiveGenerator`: best 3-line window by IDF-weighted overlap, tie-breaks per plan §7.4, ends with its citation marker
- [x] T020 [FR-010, FR-012, FR-013, FR-014, FR-015, FR-018] `QAService.ask` (core): empty-library message, top-k retrieval, score gate, coverage gate, generation, citation validation, `CitationOut` numbered by first use
- [x] T021 [FR-015, FR-016, FR-017] `OllamaGenerator`: `httpx` + `tenacity` (2 retries on connection errors, timeouts and 5xx with exponential jitter; no retry on 4xx), `LlmAnswer` strict parsing, fallback to extractive with `fallback_reason`
- [x] T022 [FR-010…FR-018] `POST /ask` with `AskRequest` validation (question 3–1000 chars, `top_k` 1–10) and `AskResponse`

## Phase 4b — Optional cloud generators (constitution 1.1.0)

- [x] T039 [FR-050, FR-053] Settings: `openai` / `anthropic` generator options, API keys as secrets (also read from `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`), model names; missing key fails startup naming the variable
- [x] T040 [FR-019, FR-015, FR-016, FR-017] `generator_cloud.py`: `OpenAIGenerator` and `AnthropicGenerator` on the official SDKs, structured output, strict `LlmAnswer` parsing, fallback to extractive on invalid output twice, API errors or refusals
- [x] T041 [FR-019, FR-054] Wiring in `deps.py`, client cleanup on shutdown, `/status` `notices` naming the cloud provider; keys never appear in any response

## Phase 4c — Optional OpenAI embeddings (constitution 1.2.0)

- [ ] T042 [FR-050, FR-052, FR-053, FR-055] Settings: `DOCBOT_EMBEDDER` (`fastembed` | `openai`), `DOCBOT_OPENAI_EMBED_MODEL`; the OpenAI embedder needs the OpenAI key
- [ ] T043 [FR-055, FR-056] `embedder_openai.py`: `OpenAIEmbedder` on the official SDK (batched, timeout, 2 retries); provider errors become an `EmbeddingUnavailable` domain error (HTTP 503)
- [ ] T044 [FR-055, FR-056, FR-054] Wiring: build the chosen embedder, re-embed at startup, fall back to keyword if that fails, `/status` notice that chunk text goes to OpenAI
- [ ] T045 [FR-055] Calibrate `DOCBOT_MIN_SCORE_VECTOR` for `text-embedding-3-small` on the sample set and document it

## Phase 5 — US-3 Generate and load the sample corpus (P2)

- [x] T023 [FR-030, FR-032] `app/adapters/samples.py`: deterministic generator for the 8 files of spec §8 and `eval/golden.yaml` (12 cases)
- [x] T024 [FR-030, FR-031] `scripts/generate_samples.py`, `POST /samples/generate`, `POST /samples/load` (generate if missing; report indexed, duplicates, failed)

## Phase 6 — US-4 Manage documents (P2)

- [x] T025 [FR-020, FR-021] `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/chunks` (404 for unknown id)
- [x] T026 [FR-022, FR-023] `DELETE /documents/{id}`: document, chunks, embeddings and file removed; retriever refreshed; test that no bulk-delete route exists
- [x] T027 [P] [FR-023] `scripts/reset_demo.py`: deletes `data/` only after typing `RESET`

## Phase 7 — US-5 Evaluate answer quality (P3)

- [x] T028 [FR-040, FR-041] `EvaluationService` (core): per-case hit / fact found / refusal correct and summary metrics
- [x] T029 [FR-040, FR-041] `POST /eval/run` (409 when the library is empty)

## Phase 8 — UI

- [x] T030 [FR-061, FR-064] `ui/api_client.py`: thin `httpx` wrapper, one consistent "API not reachable at <url>" banner
- [x] T031 [FR-060, FR-062, FR-054] `ui/Home.py` Chat page: session history, citations as `[n] file · p. X` with expandable passage and score, sidebar with retriever, generator and `top_k`
- [x] T032 [P] [FR-060, FR-063] `ui/pages/1_Documents.py`: multi-file upload, "Generate & load sample documents", table, view chunks, delete with confirmation
- [x] T033 [P] [FR-060] `ui/pages/2_Evaluate.py`: run button, `st.metric` summary, per-case ✅/❌ table
- [x] T034 [P] [FR-060, FR-051, FR-054] `ui/pages/3_Status.py`: `/status` output and how to switch retriever / generator in `.env`

## Phase 9 — Polish

- [x] T035 [SC-003, SC-004, SC-005] `tests/e2e/test_sample_corpus.py`: generate → load → 12 golden questions with keyword retriever and extractive generator
- [x] T036 [SC-007, NFR-003] README quick-start (clone to cited answer in under 10 minutes)
- [x] T037 [SC-006] Final pass: every FR has a passing test, `traceability.md` has no gaps, full quality gate green

---

## Open questions

- ~~[NEEDS CLARIFICATION] `generator_used` on a refusal~~ **Resolved 2026-10-25:** `"none"` (recorded in spec §9).
