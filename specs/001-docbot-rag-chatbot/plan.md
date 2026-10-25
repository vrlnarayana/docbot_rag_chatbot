# Implementation Plan: DocBot — RAG chatbot over PDFs, images and text files

| | |
|---|---|
| **Spec** | [spec.md](./spec.md) (SPEC-001) |
| **Branch** | `001-docbot-rag-chatbot` |
| **Status** | Reference plan |

> **Trainer note.** This is the reference "how". To demo plan generation live, delete this file and let the coding agent write its own from `spec.md` and the constitution. Then compare the agent's plan with this one.

---

## 1. Technical context

| Item | Decision |
|---|---|
| Language | Python 3.11–3.13 |
| API | FastAPI, served by Uvicorn on port 8000 |
| UI | Streamlit on port 8501, calling the API with `httpx` |
| Storage | One SQLite file (`data/docbot.db`) plus a folder of uploaded files (`data/files/`) |
| Extraction | `pypdf` for PDF text, `pypdfium2` to render scanned pages at 200 DPI, `rapidocr-onnxruntime` for OCR |
| Retrieval | **vector**: `fastembed` (`BAAI/bge-small-en-v1.5`, 384-dim) with cosine similarity in NumPy · **keyword**: `rank-bm25` |
| Generation | **extractive** (default, no LLM) · **ollama** (optional, `llama3.2:3b`, structured JSON output) |
| Packaging | `pyproject.toml` with `[project.optional-dependencies] dev = [...]`; install with `pip install -e ".[dev]"` |
| Target scale | About 100 documents and 5,000 chunks; everything fits in memory |

## 2. Constitution check

| Article | How the plan complies |
|---|---|
| I Spec is truth | FR ids in task names, test names and `traceability.md` |
| II Stack | Only the libraries listed in Article II |
| III Pure core | `app/core` holds models, ports and services only; an architecture test enforces it |
| IV Local-first | No cloud SDKs; Ollama on localhost only; synthetic samples |
| V Testing | Fake generator plus keyword retriever in unit tests; one end-to-end test on the sample corpus |
| VI Simplicity | Two processes, one SQLite file, no background workers |
| VII Dev experience | README quick-start, actionable error messages, structured logs |

Result: **PASS**, no exceptions.

## 3. Project structure

```
docbot/
├── pyproject.toml
├── .env.example
├── README.md
├── app/
│   ├── core/                      # PURE — no FastAPI, SQL, SDK or file I/O
│   │   ├── models.py              # domain + API contract models (Pydantic v2)
│   │   ├── ports.py               # Protocols: repository, file store, extractor, embedder, retriever, generator
│   │   ├── chunking.py            # page-aware chunker (FR-007)
│   │   ├── answerability.py       # IDF-weighted coverage gate (FR-012)
│   │   ├── services.py            # IngestionService, QAService, EvaluationService
│   │   └── errors.py              # domain exceptions (UnsupportedType, TooLarge, NoText, …)
│   ├── adapters/
│   │   ├── db.py                  # SQLAlchemy async engine, tables, SqliteDocumentRepository
│   │   ├── file_store.py          # LocalFileStore (generated names, safe paths)
│   │   ├── extractors.py          # PdfExtractor, ImageExtractor, TextFileExtractor + OCR helper
│   │   ├── embedder_fastembed.py  # FastEmbedEmbedder
│   │   ├── embedder_openai.py     # OpenAIEmbedder (optional, FR-055)
│   │   ├── retriever_vector.py    # VectorRetriever (NumPy cosine over cached matrix)
│   │   ├── retriever_bm25.py      # Bm25Retriever
│   │   ├── generator_extractive.py
│   │   ├── generator_ollama.py    # httpx + tenacity; strict-schema parsing
│   │   ├── generator_cloud.py     # OpenAI and Anthropic generators (official SDKs); strict-schema parsing
│   │   └── samples.py             # deterministic sample corpus + golden.yaml writer
│   ├── api/
│   │   ├── main.py                # app factory, lifespan, exception handlers, logging middleware
│   │   ├── deps.py                # build adapters ONCE from settings (DI)
│   │   └── routes/                # documents.py, ask.py, samples.py, evaluate.py, status.py
│   └── settings.py                # pydantic-settings, DOCBOT_* variables
├── ui/
│   ├── Home.py                    # Chat page
│   ├── pages/1_Documents.py
│   ├── pages/2_Evaluate.py
│   ├── pages/3_Status.py
│   └── api_client.py              # thin httpx wrapper + API-unreachable banner
├── scripts/
│   ├── generate_samples.py        # FR-030
│   └── reset_demo.py              # deletes data/ after typed confirmation (FR-023)
├── sample_data/                   # generated; git-ignored
├── eval/golden.yaml               # generated with the samples
├── data/                          # db, files, model cache; git-ignored
└── tests/
    ├── conftest.py                # tmp db/storage, keyword retriever, FakeGenerator, sample corpus fixture
    ├── unit/                      # chunking, answerability, services with fakes
    ├── api/                       # endpoint contract tests via httpx.AsyncClient + ASGITransport
    └── e2e/test_sample_corpus.py  # SC-003, SC-004, SC-005
```

## 4. Settings (`DOCBOT_` prefix, `.env` supported)

| Variable | Default | Notes |
|---|---|---|
| `DOCBOT_DATA_DIR` | `./data` | Holds `docbot.db`, `files/` and `models/` |
| `DOCBOT_SAMPLE_DIR` | `./sample_data` | |
| `DOCBOT_MAX_UPLOAD_MB` | `20` | FR-003, all types except PDF |
| `DOCBOT_MAX_PDF_MB` | `1` | FR-003, PDF only |
| `DOCBOT_CHUNK_SIZE` / `DOCBOT_CHUNK_OVERLAP` | `800` / `100` | FR-007 |
| `DOCBOT_RETRIEVER` | `vector` | `vector` \| `keyword` (FR-011, FR-052) |
| `DOCBOT_EMBEDDER` | `fastembed` | `fastembed` (local) \| `openai` (FR-055) |
| `DOCBOT_EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | fastembed model; cached in `data/models` |
| `DOCBOT_OPENAI_EMBED_MODEL` | `text-embedding-3-small` | Used when `EMBEDDER=openai`; needs the OpenAI key (FR-053) |
| `DOCBOT_TOP_K` | `4` | Allowed 1–10 |
| `DOCBOT_MIN_SCORE_VECTOR` | `0.50` | Cosine; tune using the evaluation page. Measured on the sample set (2026-10-25): with `text-embedding-3-small`, answerable questions score 0.52–0.79 and out-of-scope ones 0.27–0.51; 0.50 and 0.45 both give 100 % on the golden set. Use 0.45 for more headroom on your own documents. |
| `DOCBOT_MIN_SCORE_KEYWORD` | `1.0` | BM25 |
| `DOCBOT_MIN_COVERAGE` | `0.55` | Answerability gate (§7.2) |
| `DOCBOT_GENERATOR` | `extractive` | `extractive` \| `ollama` \| `openai` \| `anthropic` (FR-013, FR-019, FR-052) |
| `DOCBOT_OLLAMA_URL` | `http://localhost:11434` | |
| `DOCBOT_OLLAMA_MODEL` | `llama3.2:3b` | Any instruct model pulled into Ollama |
| `DOCBOT_LLM_TIMEOUT_S` | `30` | FR-017 |
| `DOCBOT_OPENAI_API_KEY` (or `OPENAI_API_KEY`) | — | Required when `GENERATOR=openai` (FR-053) |
| `DOCBOT_OPENAI_MODEL` | `gpt-5-mini` | Any chat model the key can use that supports structured outputs |
| `DOCBOT_ANTHROPIC_API_KEY` (or `ANTHROPIC_API_KEY`) | — | Required when `GENERATOR=anthropic` (FR-053) |
| `DOCBOT_ANTHROPIC_MODEL` | `claude-opus-5-5` | |
| `DOCBOT_API_URL` | `http://localhost:8000` | Used by the UI |

Any value outside the allowed options (e.g. `DOCBOT_GENERATOR=azure_openai`) stops startup with: `Unknown generator 'azure_openai'. Valid options: extractive, ollama, openai, anthropic. (Azure arrives in SPEC-002.)`

## 5. Data model (SQLite)

**documents**

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID4 |
| filename | TEXT | Original name, display only |
| stored_name | TEXT UNIQUE | `<uuid>.<ext>` |
| doc_type | TEXT | `pdf` \| `image` \| `text` |
| mime_type | TEXT | |
| size_bytes | INTEGER | |
| sha256 | TEXT UNIQUE | FR-008 |
| page_count | INTEGER | |
| ocr_page_count | INTEGER | |
| chunk_count | INTEGER | |
| status | TEXT | `indexed` (failed uploads are not stored) |
| created_at | TEXT | ISO 8601, UTC |

**chunks**

| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID4 |
| document_id | TEXT FK → documents.id | `ON DELETE CASCADE` |
| page | INTEGER | 1-based |
| ordinal | INTEGER | Order within the document |
| source | TEXT | `text` \| `ocr` |
| text | TEXT | |
| embedding | BLOB NULL | float32 bytes; null when the keyword retriever is active |
| embed_model | TEXT NULL | Re-embed on startup if it differs from the configured model |

Enable `PRAGMA foreign_keys = ON` on every connection. Index `chunks(document_id)`.

## 6. API contract

All bodies are JSON unless noted. Every route declares `response_model`. Errors use one shape: `ErrorResponse {code: str, message: str}`.

| Method & path | Request | Response | Status codes | FR |
|---|---|---|---|---|
| `GET /health` | — | `HealthResponse {status: "ok"}` | 200 | — |
| `GET /status` | — | `StatusResponse {retriever, generator, embed_model, documents, chunks, fallbacks: list[str]}` | 200 | FR-051 |
| `POST /documents` | multipart `file` | `UploadResponse {document: DocumentOut, duplicate: bool}` | 201 new · 200 duplicate · 413 · 415 · 422 | FR-001…009 |
| `GET /documents` | — | `list[DocumentOut]` | 200 | FR-020 |
| `GET /documents/{id}` | — | `DocumentOut` | 200 · 404 | FR-020 |
| `GET /documents/{id}/chunks` | — | `list[ChunkOut]` | 200 · 404 | FR-021 |
| `DELETE /documents/{id}` | — | `DeleteResponse {deleted_id}` | 200 · 404 | FR-022, FR-023 |
| `POST /ask` | `AskRequest {question: str[2..1000], top_k: int[1..10] = 4, history: list[ChatTurn] (≤ 6) = []}` | `AskResponse` | 200 · 422 | FR-010…018, FR-070…073 |
| `POST /samples/generate` | — | `SamplesResponse {files: list[str]}` | 200 | FR-030 |
| `POST /samples/load` | — | `LoadSamplesResponse {indexed, duplicates, failed: list[FailedFile]}` | 200 | FR-031 |
| `POST /eval/run` | `EvalRequest {top_k: int = 4}` | `EvalRunResponse {summary: EvalSummary, results: list[EvalCaseResult]}` | 200 · 409 if no docs | FR-040, FR-041 |

**Key response models**

```text
DocumentOut     id, filename, doc_type, size_bytes, page_count, ocr_page_count, chunk_count, status, created_at
ChunkOut        id, page, ordinal, source, text
CitationOut     n, chunk_id, document_id, filename, page, score, passage
ChatTurn        role: "user" | "assistant", content: str[1..2000]
AskResponse     answer, grounded, citations: list[CitationOut], retriever, generator_used,
                fallback_reason: str | None, latency_ms, standalone_question: str | None,
                small_talk: bool
EvalCaseResult  question, expected_file, expected_page, retrieved_files, hit, fact_found,
                expect_refusal, refused, refusal_correct
EvalSummary     cases, hit_rate_at_k, answer_accuracy, refusal_accuracy, retriever, generator, top_k
```

`DocumentOut` never includes `stored_name`, `sha256` or any file path (NFR-006).

## 7. Core algorithms

### 7.1 Ingestion (`IngestionService.ingest`)
1. Check the size limit before reading the whole stream (FR-003), then the extension (FR-002). PDFs have their own, lower limit (`MAX_PDF_MB`), enforced while the file is read.
2. Compute SHA-256; if a document with that hash exists, return it with `duplicate=True` (FR-008).
3. Extract pages in a worker thread:
   - **PDF**: for each page, `pypdf` text with `extraction_mode="layout"` so table rows stay on one line; then collapse runs of 2+ spaces inside a line to ` | ` (e.g. `Front | 276 mm | 3.5 mm`). If under 20 characters (after stripping), render with `pypdfium2` at 200 DPI and OCR it (FR-004).
   - **Image**: OCR the whole image as page 1 (FR-005).
   - **Text / Markdown**: decode UTF-8, then Latin-1; page 1 (FR-006).
   - OCR lines are joined in reading order (top-to-bottom, then left-to-right).
4. If all pages are empty, raise `NoTextExtracted` → 422 (FR-009).
5. Chunk each page separately (§7.3); embed chunks if the vector retriever is active (worker thread).
6. Save the file under a generated name, then insert the document and chunks in one transaction. If the insert fails, delete the saved file.
7. Tell the retriever to refresh its cache.

### 7.2 Answering (`QAService.ask`)
1. If there are no chunks, return the "load the sample set" message (FR-018).
2. Retrieve the top *k* chunks with scores (FR-010).
3. **Score gate:** if the best score is below `MIN_SCORE_<retriever>`, refuse (FR-012).
4. **Answerability gate:** tokenise the question (lower-case, split on non-alphanumerics, drop stop-words — including question words such as *what, which, who, how, many, much, does, is, the, for, of* — and strip a trailing `s`). Weight each term by its IDF over all chunks; a term in no chunk gets the maximum IDF. Coverage = (sum of weights of terms found in the retrieved chunks) ÷ (sum of all weights). If coverage is below `MIN_COVERAGE`, refuse. This stops "top speed of the Velo 125" from passing just because "Velo 125" appears in the corpus.
5. Generate with the configured generator (§7.4), wrapped in the resilient client for Ollama.
6. Validate the citations (FR-015) and build `CitationOut` items numbered in order of first use.

### 7.2b Conversation (FR-070 to FR-073)
1. **Small talk first:** a short message that is only a greeting, thanks, goodbye or "what can you do / help" gets a fixed friendly reply (`small_talk = true`, `generator_used = "none"`), with no retrieval.
2. **Follow-ups:** with history, rewrite the question into a standalone one. An LLM generator is asked to return `{"question": str}` (strict); otherwise, or on failure, the local rule prepends the previous user question when the new one looks like a follow-up (starts with "and", "what about", "how about", "also"; uses it/its/that/they/them/those/this/one; or has fewer than 3 content words).
3. Steps 1–6 of §7.2 then run on the standalone question. LLM generators get a conversational system prompt.

### 7.3 Chunking
Split each page's text into chunks of at most `CHUNK_SIZE` characters with `CHUNK_OVERLAP` overlap. Split at blank lines first, then single newlines, then sentence ends, then spaces. Never cross a page. Drop chunks under 20 characters unless they are the page's only text.

### 7.4 Generators
- **Extractive** (default): split each retrieved chunk into lines (and long lines into sentences). Score every window of up to 3 consecutive lines by IDF-weighted overlap with the question terms; ties go to the higher-ranked chunk, then the earlier window. Return the best window followed by its citation marker. A window is used so that a table header and its value row come back together, e.g. `Position | Disc diameter | Minimum thickness` / `Front | 276 mm | 3.5 mm [1]`. Deterministic, with no network access.
- **Ollama**: `POST {OLLAMA_URL}/api/chat` with `stream: false`, `options.temperature: 0`, and `format` set to the JSON schema of `LlmAnswer {answer: str, citations: list[int], grounded: bool}` (strict, `extra="forbid"`). The system prompt says: answer only from the numbered passages; cite passages as `[n]`; if the passages do not contain the answer, set `grounded` to false. Parse with `LlmAnswer.model_validate_json(..., strict=True)`. Retry transient errors (connection errors, timeouts, 5xx) up to 2 times with `wait_exponential_jitter`; never retry 4xx. If validation fails twice, or no valid citations remain, fall back to extractive (FR-016, FR-017).

- **OpenAI / Anthropic** (optional, FR-019): same system prompt, numbered passages and `LlmAnswer` schema as Ollama, requested as structured output (OpenAI `response_format` json_schema with `strict: true`; Anthropic `output_config.format` json_schema). The SDKs' own retries cover transient errors (2 retries, exponential backoff with jitter) and the client timeout is `DOCBOT_LLM_TIMEOUT_S`. Parse with `LlmAnswer.model_validate_json(..., strict=True)`; invalid output twice, an API error, or a Claude `refusal` stop reason falls back to extractive with a `fallback_reason`. Claude requests opt into server-side refusal fallback (`fallbacks: "default"`).

## 8. Sample generator (`app/adapters/samples.py`)
- Pure function `generate(target_dir) -> list[Path]`, deterministic: fixed text, fixed image sizes, no timestamps. PDF metadata dates are fixed via ReportLab's `invariant=1`.
- **Text PDFs**: ReportLab `SimpleDocTemplate`. The brake standard's page 2 uses a `Table` whose rows read as plain lines when extracted (e.g. `Front | Minimum thickness | 3.5 mm`).
- **Scanned PDF**: draw the certificate text onto a 1654 × 2339 px white Pillow image (A4 at 200 DPI) in a large, clear font, add slight noise, and save with `Image.save(..., "PDF", resolution=200)`. The result has no text layer.
- **Images**: Pillow; the spec sheet is a clean table-like layout; the label has a border and slightly smaller text. Use a TrueType font bundled with Pillow or a common system font, with fallback to `ImageFont.load_default(size=…)`.
- **Wording**: state each fact in a natural sentence or table row that uses the golden question's key terms (e.g. "Recommended tyre pressure (solo rider): front 29 psi, rear 33 psi"; "DVP&R completion required to exit Gate G3: ≥ 95%"). Do not mention top speed, the CEO or battery warranty anywhere, so the three refusal cases stay out of the corpus.
- **golden.yaml**: the 12 cases from spec §8.

## 9. UI (Streamlit)
- **Chat (Home.py)**: chat history in `st.session_state`; each assistant message shows the answer, then citations as `[n] filename · p. X`, each in an `st.expander` with the passage and score. A sidebar shows the retriever, generator and a `top_k` slider.
- **Documents**: an uploader for multiple files; "Generate & load sample documents"; a table of documents; per-row "View chunks" (dialog or expander) and "Delete" with a confirm step.
- **Evaluate**: a "Run evaluation" button; summary metrics with `st.metric`; per-case table with ✅/❌.
- **Status**: the output of `/status`, plus how to switch retriever or generator through `.env`.
- Every API call goes through `ui/api_client.py`, which shows one consistent banner when the API is down (FR-064).

## 10. Test plan

| Area | Tests | Covers |
|---|---|---|
| Unit — chunking | size, overlap, no page crossing, split preference | FR-007 |
| Unit — answerability | out-of-corpus terms refused; in-corpus question passes | FR-012 |
| Unit — QA service | fake retriever and generator; citation validation; fallback path; empty library | FR-010, 013–018 |
| Unit — Ollama adapter | `httpx.MockTransport`: valid JSON, invalid JSON twice → fallback, 503 → retry, 400 → no retry | FR-015–017 |
| API contract | each endpoint: status code plus response parses into its model; no forbidden fields | FR-001–009, 020–023, 040–041, 051–052 |
| Architecture | `app/core` imports none of the banned modules | Constitution III.10 |
| End-to-end | generate samples → load → ask the 12 golden questions with the keyword retriever and extractive generator → SC-003, SC-004, SC-005 | SC-003–005 |

## 11. Run commands

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python scripts/generate_samples.py                     # writes sample_data/ and eval/golden.yaml
uvicorn app.api.main:app --reload --port 8000          # terminal 1
streamlit run ui/Home.py                               # terminal 2
pytest && ruff check . && mypy --strict app/core       # quality gate
python scripts/reset_demo.py                           # wipe data/ (asks you to type RESET)
```

## 12. Phases (input to `/speckit.tasks`)
1. **Setup**: `pyproject.toml`, layout, settings, logging, `.gitignore`, `.env.example`.
2. **Foundation**: core models and ports, SQLite adapter, file store, app factory, `/health`, `/status`, architecture test.
3. **US-1 Upload**: extractors and OCR, chunking, ingestion service, `/documents` POST.
4. **US-2 Ask**: retrievers, answerability gate, extractive generator, Ollama generator, `/ask`.
5. **US-3 Samples**: generator, `scripts/generate_samples.py`, `/samples/*`.
6. **US-4 Manage**: list, chunks, delete endpoints.
7. **US-5 Evaluate**: evaluation service, `/eval/run`.
8. **UI**: the four Streamlit pages and the API client.
9. **Polish**: README quick-start, end-to-end test, `traceability.md`, final quality gate.
