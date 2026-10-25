# Feature Specification: DocBot — RAG chatbot over PDFs, images and text files

| | |
|---|---|
| **Spec ID** | SPEC-001 |
| **Feature branch** | `001-docbot-rag-chatbot` |
| **Status** | Ready for planning |
| **Created** | 2026-10-25 |
| **Training context** | Day 2 · Use case 1 · Module 1 — built live with a coding agent to show Spec-Driven Development |
| **Constitution** | `.specify/memory/constitution.md` |
| **Next spec** | SPEC-002 will add Azure adapters (Blob Storage, AI Search, Content Understanding, Azure OpenAI). **Not part of this spec.** |

---

## 1. Why

R&D engineers lose time hunting for facts that already exist in documents: a brake-disc wear limit buried in a table, a torque value on a scanned supplier certificate, a part number on a label photo, or a change note in a text file. Keyword search fails on scans and images, and generic chatbots make up answers.

**DocBot** lets an engineer upload a mixed set of documents and ask questions in plain English. Every answer cites the document and page it came from. If the answer is not in the documents, DocBot says so instead of guessing.

This first version runs entirely on a laptop with no cloud services, so learners can see each stage of a RAG pipeline (upload → parse → index → answer) and test it before it moves to Azure in SPEC-002.

## 2. Scope

**In scope**
- Uploading PDF (text and scanned), PNG/JPG images, and TXT/MD files.
- Extracting text, including OCR for images and scanned PDF pages, with page numbers.
- Splitting text into chunks, indexing them, and retrieving the most relevant ones.
- Answering questions with citations, and refusing when the documents do not contain the answer.
- A generator for a synthetic sample corpus and a golden question set.
- An evaluation run that scores retrieval and answers against the golden set.
- A Streamlit UI that talks only to the FastAPI service.
- Optional cloud generators (OpenAI, Anthropic Claude) using the user's own API key, off by default.

**Out of scope (for this spec)**
- Azure services, and any cloud service other than the optional OpenAI and Anthropic generators (SPEC-002).
- Login, user accounts, multi-tenant access control.
- Word, Excel, PowerPoint, CAD or email files.
- Understanding diagrams or photos beyond the text OCR can read from them.
- Conversation memory: each question is answered independently. The UI shows the session's history, but the server does not use it.
- Streaming responses, fine-tuning, agents and tool calling.

## 3. User scenarios & testing

Priorities: **P1** = the demo fails without it. **P2** = expected in the demo. **P3** = nice to show if time allows. Each story can be built and tested on its own.

### US-1 — Upload documents (P1)

An engineer uploads a PDF, an image or a text file and sees it in the document list with its page and chunk counts.

**Why P1:** Nothing can be asked until documents are indexed.

**Independent test:** Upload one file of each supported type through the API and confirm each appears with `status = indexed` and at least one chunk.

**Acceptance scenarios**
1. **Given** an empty library, **when** the engineer uploads `DM-STD-BRK-001_Brake_System_Design_Standard.pdf`, **then** it appears with 3 pages, ≥ 3 chunks, and `status = indexed`.
2. **Given** a PNG of a spec sheet, **when** it is uploaded, **then** its OCR text is stored as page 1 with `source = ocr`.
3. **Given** a PDF page with no text layer, **when** it is uploaded, **then** that page is OCR'd and its chunks are marked `source = ocr`.
4. **Given** a file already in the library, **when** the same bytes are uploaded again, **then** no duplicate is created and the response says `duplicate = true` and gives the existing document id.
5. **Given** a `.docx` file, **when** it is uploaded, **then** it is rejected with a message listing the supported types.

### US-2 — Ask a question and get a cited answer (P1)

An engineer types a question and gets a short answer with numbered citations. Each citation shows the file name and page, and can be expanded to show the passage used.

**Why P1:** This is the core value, and it is what the training slide promises.

**Independent test:** With the sample corpus loaded, ask the golden questions and check that answers contain the expected facts and cite the expected document and page.

**Acceptance scenarios**
1. **Given** the sample corpus, **when** asked *"What is the minimum thickness of the front brake disc?"*, **then** the answer contains `3.5 mm` and cites `DM-STD-BRK-001…pdf`, page 2. (This fact is in a table.)
2. **Given** the sample corpus, **when** asked *"What is the tensile strength on the Northwind Castings certificate?"*, **then** the answer contains `240 MPa` and cites the scanned certificate PDF, page 1. (This fact is only in OCR text.)
3. **Given** the sample corpus, **when** asked *"What is the high beam wattage of the LED headlamp?"*, **then** the answer contains `13 W` and cites the headlamp spec-sheet image. (This fact is only in an image.)
4. **Given** the sample corpus, **when** asked *"What is the top speed of the Velo 125?"* (not in any document), **then** DocBot answers *"I couldn't find this in the uploaded documents."*, returns no citations, and marks the response `grounded = false`.
5. **Given** an empty library, **when** any question is asked, **then** DocBot says there are no documents yet and suggests loading the sample set.

### US-3 — Generate and load the sample corpus (P2)

A trainer clicks one button, or runs one command, to generate the synthetic sample documents and index them.

**Why P2:** It makes the demo repeatable on any laptop, without real company data.

**Independent test:** Run the generator into an empty folder and confirm it creates exactly the 8 files in §8 and the golden set; load them and confirm all 8 are indexed.

**Acceptance scenarios**
1. **Given** an empty `sample_data/` folder, **when** the generator runs, **then** the 8 files listed in §8 and `eval/golden.yaml` are created.
2. **Given** the generator has run twice, **then** the generated files are identical both times (deterministic output).
3. **Given** the samples exist, **when** "Load sample documents" is clicked, **then** all 8 are indexed; files already indexed are reported as duplicates, not re-indexed.

### US-4 — Manage documents (P2)

An engineer sees the indexed documents, opens one to inspect its chunks (page, source, text), and deletes a document they no longer need.

**Why P2:** Seeing the chunks is how learners understand why retrieval works or fails.

**Independent test:** List documents, open one, read its chunks, delete it, and confirm its chunks no longer appear in any answer.

**Acceptance scenarios**
1. **Given** indexed documents, **when** the Documents page opens, **then** each shows file name, type, pages, chunks, OCR pages, size and upload time.
2. **Given** a document, **when** "View chunks" is opened, **then** every chunk shows its page number, source (`text` or `ocr`) and full text.
3. **Given** a document, **when** it is deleted and the deletion is confirmed, **then** the document, its chunks and its stored file are removed, and later answers never cite it.

### US-5 — Evaluate answer quality (P3)

A trainer runs the golden question set and sees how many questions found the right source, contained the right fact, and correctly refused out-of-scope questions.

**Why P3:** It shows learners that RAG quality is measured, not judged by eye.

**Independent test:** Run the evaluation on the sample corpus and confirm it returns one result per golden question plus summary metrics.

**Acceptance scenarios**
1. **Given** the sample corpus and golden set, **when** the evaluation runs, **then** each question shows: expected source, retrieved sources, hit (yes/no), fact found (yes/no), refusal correct (yes/no).
2. **Given** a completed run, **then** summary metrics show hit rate @ k, answer accuracy and refusal accuracy as percentages.
3. **Given** the retriever setting is changed (vector ↔ keyword), **when** the evaluation runs again, **then** the results reflect the new retriever, so the two can be compared side by side.

### Edge cases
- An empty file, or a PDF with zero extractable text where OCR also finds nothing → rejected with a clear message; nothing is stored.
- A file over the size limit → rejected before it is read into memory.
- An encrypted or corrupted PDF → rejected with a clear message; the service keeps running.
- An image where OCR finds no text → rejected as "no readable text".
- A very short question (fewer than 3 characters) or a very long one (over 1,000 characters) → validation error.
- A file name with spaces, non-English characters or path segments (`../`) → stored under a safe generated name; the original name is kept for display only.
- An Ollama generator that is selected but not running → the answer falls back to extractive mode and the response says so (`generator_used = extractive`, `fallback_reason` filled).
- The embedding model cannot be downloaded on first run → the service starts with the keyword retriever, and the status page says why.

## 4. Functional requirements

Requirements use EARS notation. Each one gets at least one test named after it (see the constitution, Article I).

### Ingestion
- **FR-001** WHEN a file with extension `.pdf`, `.png`, `.jpg`, `.jpeg`, `.txt` or `.md` is uploaded, THE SYSTEM SHALL extract its text page by page and store it as an indexed document.
- **FR-002** WHEN a file of any other type is uploaded, THE SYSTEM SHALL reject it with HTTP 415 and list the supported types.
- **FR-003** WHEN an uploaded file is larger than the configured limit for its type (PDF: default 1 MB; other types: default 20 MB), THE SYSTEM SHALL reject it with HTTP 413 without storing it.
- **FR-004** WHEN a PDF page has fewer than 20 characters of extractable text, THE SYSTEM SHALL render that page to an image, run OCR on it, and mark its chunks `source = ocr`.
- **FR-005** WHEN an image is uploaded, THE SYSTEM SHALL run OCR on it and store the result as page 1 with `source = ocr`.
- **FR-006** WHEN a `.txt` or `.md` file is uploaded, THE SYSTEM SHALL treat the whole file as page 1, decoding it as UTF-8 and falling back to Latin-1.
- **FR-007** WHEN text is extracted, THE SYSTEM SHALL split it into chunks of at most 800 characters, overlapping by 100 characters, without crossing page boundaries and preferring paragraph or line breaks as split points.
- **FR-008** WHEN a file with the same SHA-256 hash as an existing document is uploaded, THE SYSTEM SHALL NOT re-index it, and SHALL return the existing document with `duplicate = true`.
- **FR-009** IF extraction produces no text for the whole file, THEN THE SYSTEM SHALL reject the upload with HTTP 422 and store nothing.

### Retrieval and answering
- **FR-010** WHEN a question is asked, THE SYSTEM SHALL retrieve the top *k* chunks (default 4, allowed 1–10) using the configured retriever.
- **FR-011** THE SYSTEM SHALL support two retrievers behind one interface: **vector** (local embeddings with cosine similarity) and **keyword** (BM25).
- **FR-012** IF the best retrieved chunk scores below the configured threshold for that retriever, THEN THE SYSTEM SHALL refuse with *"I couldn't find this in the uploaded documents."*, return no citations, set `grounded = false`, and not call the generator.
- **FR-013** WHEN the retrieved chunks pass the threshold, THE SYSTEM SHALL produce an answer using only those chunks, through the configured generator: **extractive** (default, no LLM) or **ollama** (a local LLM).
- **FR-014** THE SYSTEM SHALL return each answer with numbered citations; each citation has document id, file name, page number, chunk id, score and the passage text.
- **FR-015** WHEN an LLM generator returns output, THE SYSTEM SHALL parse it into a strict schema (answer text, cited chunk numbers, grounded flag) and discard any citation that does not refer to a chunk that was supplied.
- **FR-016** IF LLM output fails schema validation twice, or no valid citations remain, THEN THE SYSTEM SHALL fall back to the extractive generator and report `generator_used = extractive` with a `fallback_reason`.
- **FR-017** IF the selected generator is unavailable (not running, timed out after 30 s, or erroring), THEN THE SYSTEM SHALL retry transient errors up to 2 times with exponential backoff and jitter, and then fall back as in FR-016.
- **FR-018** WHEN no documents are indexed, THE SYSTEM SHALL return a message suggesting the sample corpus be loaded, and SHALL NOT run retrieval.
- **FR-019** WHERE the generator is set to **openai** or **anthropic**, THE SYSTEM SHALL produce answers through that provider's API with the user's API key, applying the same strict schema, citation validation, retries and extractive fallback as FR-015 to FR-017.

### Document management
- **FR-020** THE SYSTEM SHALL list all documents with id, file name, type, size, page count, chunk count, OCR page count, status and upload time.
- **FR-021** WHEN a document's chunks are requested, THE SYSTEM SHALL return each chunk's id, page, source and text, in page order.
- **FR-022** WHEN a single document is deleted by id, THE SYSTEM SHALL remove the document, its chunks, its embeddings and its stored file in one transaction.
- **FR-023** THE SYSTEM SHALL NOT expose any API that deletes more than one document per call. Resetting the demo is a local command-line script only.

### Sample data
- **FR-030** THE SYSTEM SHALL provide a command that generates the 8 sample documents in §8 and `eval/golden.yaml` into `sample_data/`, deterministically.
- **FR-031** WHEN "load samples" is requested, THE SYSTEM SHALL ingest every file in `sample_data/`, generating them first if missing, and report indexed and duplicate counts.
- **FR-032** All sample content SHALL be fictional (company "Demo Motors", model "Velo 125") and contain no real company data.

### Evaluation
- **FR-040** WHEN an evaluation run is requested, THE SYSTEM SHALL ask every question in `eval/golden.yaml` and, for each, report: hit (expected file among retrieved sources), fact found (all expected keywords in the answer, case-insensitive), and refusal correct (for questions marked `expect_refusal`).
- **FR-041** THE SYSTEM SHALL report summary metrics: hit rate @ k, answer accuracy, refusal accuracy, and the retriever and generator used.

### Configuration and status
- **FR-050** THE SYSTEM SHALL read all settings from environment variables or a `.env` file, with the defaults listed in the plan.
- **FR-051** WHEN started, THE SYSTEM SHALL report on a status endpoint the active retriever, generator, embedding model, document and chunk counts, and any fallback in force.
- **FR-052** IF a generator or retriever name that is not implemented is configured (for example `azure_openai`), THEN THE SYSTEM SHALL fail at startup with a message naming the valid options.
- **FR-053** IF a cloud generator is selected without its API key, THEN THE SYSTEM SHALL fail at startup with a message naming the environment variable to set.
- **FR-054** WHILE a cloud generator is active, THE SYSTEM SHALL say so on the status endpoint and in the UI, naming the provider that receives the question and the retrieved passages.

### User interface
- **FR-060** THE SYSTEM SHALL provide a Streamlit UI with four pages: **Chat**, **Documents**, **Evaluate** and **Status**.
- **FR-061** The UI SHALL call only the FastAPI service over HTTP; it SHALL NOT read the database or files directly.
- **FR-062** WHEN an answer is shown, THE UI SHALL show its citations as `[n] file name · p. X`, each expandable to show the passage and score.
- **FR-063** WHEN a delete is requested in the UI, THE UI SHALL ask for confirmation before calling the API.
- **FR-064** WHEN the API is not reachable, THE UI SHALL show a clear banner with the expected API URL instead of a stack trace.

## 5. Non-functional requirements
- **NFR-001 Local-first.** After installation and the first embedding-model download, the app runs with no internet. No document text leaves the machine unless the user selects a cloud generator; then only the question and the retrieved passages are sent to that provider.
- **NFR-002 Performance.** On a typical laptop CPU, the full sample corpus is indexed in under 60 s, and an extractive answer returns in under 3 s.
- **NFR-003 Simple to run.** One install command, then two commands to start (API and UI). No Docker and no database server.
- **NFR-004 Cross-platform.** Works on Windows, macOS and Linux with Python 3.11–3.13.
- **NFR-005 Ready for SPEC-002.** Storage, extraction, retrieval and generation each sit behind an interface the core owns, so Azure can be added as new adapters without changing the core.
- **NFR-006 Safe responses.** API responses never include raw prompts, file-system paths or stack traces.

## 6. Key entities
- **Document** — one uploaded file: id, original file name, stored name, type, size, SHA-256, page count, status, uploaded at.
- **Chunk** — a piece of a document's text: id, document id, page number, position, source (`text` | `ocr`), text, embedding (vector retriever only).
- **Citation** — the link from an answer to a chunk: number shown to the user, chunk id, document id, file name, page, score, passage.
- **Answer** — question, answer text, citations, grounded flag, retriever used, generator used, optional fallback reason, timing.
- **Golden case** — question, expected file, expected page, expected keywords, `expect_refusal`.
- **Evaluation result** — per-case outcomes plus summary metrics.

## 7. Success criteria
Measured with the sample corpus and golden set (§8):
- **SC-001** Hit rate @ 4 is at least **80%** with the vector retriever.
- **SC-002** Answer accuracy is at least **80%** on answerable questions, using the extractive generator.
- **SC-003** All **3** out-of-scope questions are refused.
- **SC-004** **100%** of non-refused answers carry at least one citation that points to a real chunk.
- **SC-005** The table question (US-2 #1), the scanned-PDF question (US-2 #2) and the image question (US-2 #3) are all answered correctly.
- **SC-006** Every functional requirement has at least one passing test, and `traceability.md` shows no gaps.
- **SC-007** A learner who has never seen the code can start the app and get a cited answer within 10 minutes of cloning, following the README.

## 8. Sample corpus (generated, fictional)

Company **Demo Motors**, motorcycle model **Velo 125**. The generator must put these facts in exactly the locations shown, because the golden set depends on them.

| # | File | Type | Pages | Key facts and where they are |
|---|---|---|---|---|
| 1 | `DM-STD-BRK-001_Brake_System_Design_Standard.pdf` | PDF, text | 3 | p.1 scope and purpose. **p.2 table** "Brake disc specifications": front disc diameter **276 mm**, front minimum thickness **3.5 mm**; rear disc diameter **220 mm**, rear minimum thickness **4.0 mm**. p.3 brake fluid **DOT 4**, replace every **2 years or 20,000 km**. |
| 2 | `TR-2026-014_Handlebar_Vibration_Test_Report.pdf` | PDF, text | 2 | p.1 test set-up. p.2 result: peak handlebar vibration **18.2 m/s²** at **6,500 rpm**; acceptance limit **≤ 20 m/s²**; verdict **PASS**. |
| 3 | `SC-889_Supplier_Certificate_Northwind_Castings.pdf` | PDF, **scanned** (image only, no text layer) | 1 | Supplier **Northwind Castings**; material **AlSi10Mg**; tensile strength **240 MPa**; certificate valid until **31 March 2027**. |
| 4 | `DM-SPEC-LMP-12_Headlamp_Spec_Sheet.png` | Image | 1 | LED headlamp; **12 V**; low beam **9 W**; high beam **13 W**; ingress rating **IP67**. |
| 5 | `Label_DM-BRK-2210_Front_Caliper.jpg` | Image (photo-style label) | 1 | Part no. **DM-BRK-2210**; front brake caliper; **2-piston**; supplier code **NWC**. |
| 6 | `DM-ECN-0457_Engineering_Change_Note.txt` | Text | 1 | Rear sprocket on Velo 125 changes from **42T to 43T**, effective **1 November 2026**; reason: better low-end torque on hill climbs. |
| 7 | `Velo125_Owner_Manual_Extract.md` | Markdown | 1 | Tyre pressure, solo rider: front **29 psi**, rear **33 psi**. Engine oil **SAE 10W-30**, capacity **1.0 L**. |
| 8 | `DM-GATE-G3_Readiness_Checklist.md` | Markdown | 1 | Gate G3 exit criteria: DVP&R completion **≥ 95%**; open DFMEA items with RPN > 100 must be **0**; PPAP status **submitted** for all critical parts. |

**Golden set (`eval/golden.yaml`, 12 cases):**

| # | Question | Expected file | Page | Expected keywords |
|---|---|---|---|---|
| 1 | What is the minimum thickness of the front brake disc? | 1 | 2 | `3.5 mm` |
| 2 | What brake fluid does the brake standard specify? | 1 | 3 | `DOT 4` |
| 3 | What was the peak handlebar vibration in the test? | 2 | 2 | `18.2` |
| 4 | What is the tensile strength on the Northwind Castings certificate? | 3 | 1 | `240 MPa` |
| 5 | What is the high beam wattage of the LED headlamp? | 4 | 1 | `13 W` |
| 6 | How many pistons does the front brake caliper have? | 5 | 1 | `2` |
| 7 | What is the new rear sprocket size for the Velo 125? | 6 | 1 | `43T` |
| 8 | What is the recommended rear tyre pressure? | 7 | 1 | `33 psi` |
| 9 | What DVP&R completion is required to exit Gate G3? | 8 | 1 | `95%` |
| 10 | What is the top speed of the Velo 125? | — | — | *refusal expected* |
| 11 | Who is the CEO of Demo Motors? | — | — | *refusal expected* |
| 12 | What is the warranty period for the battery? | — | — | *refusal expected* |

## 9. Clarifications

### Session 2026-10-25
- **Q:** Which LLM runs the answers when there is no cloud? → **A:** By default, an **extractive** generator that quotes the best-matching sentences with citations and needs no LLM. **Ollama** is an optional local LLM. The cloud model arrives in SPEC-002.
- **Q:** Where are embeddings stored? → **A:** In the same SQLite file as the documents and chunks. With a few thousand chunks, an in-memory cosine search is fast enough, and there is no vector database to install.
- **Q:** How are scanned pages detected? → **A:** A PDF page with fewer than 20 characters of extractable text is treated as scanned (FR-004).
- **Q:** Should ingestion be a background job? → **A:** No. The upload request waits for indexing to finish, which keeps the demo simple. CPU-heavy steps (OCR, embedding) run in a worker thread so the API stays responsive.
- **Q:** Is chat history sent with each question? → **A:** No. Each question is answered on its own (see Scope).
- **Q:** Should PDFs have their own size limit? → **A:** Yes. PDFs are capped at **1 MB** by default (`DOCBOT_MAX_PDF_MB`), because every page without a text layer is rendered and OCR'd, so a large PDF can tie up the CPU for a long time. Other types keep the 20 MB limit. (Amends FR-003.)
- **Q:** What is `generator_used` when DocBot refuses or the library is empty and no generator runs? → **A:** `"none"`. It reports truthfully that no generator produced the text (FR-012, FR-018).
- **Q:** Can users bring their own OpenAI or Claude key? → **A:** Yes (constitution 1.1.0). `DOCBOT_GENERATOR=openai` or `anthropic`, with `DOCBOT_OPENAI_API_KEY` / `OPENAI_API_KEY` or `DOCBOT_ANTHROPIC_API_KEY` / `ANTHROPIC_API_KEY`. Off by default; the status page and UI show when a cloud provider is in use (FR-019, FR-053, FR-054).
- **Q:** Can learners use real Hero documents? → **A:** Not in the demo. In their own department lab they may upload non-confidential documents through the same UI.
