# DocBot spec pack — trainer guide

A ready-to-build specification for **DocBot**, a local RAG chatbot over PDFs, images and text files. You give this folder to Claude Code, and it builds the app from the spec while learners watch the Spec-Driven Development workflow: constitution → spec → plan → tasks → implement → verify.

- **Stack:** FastAPI · SQLite · Streamlit · local OCR and embeddings · optional Ollama
- **Cloud:** none. Azure arrives later as SPEC-002, through new adapters only.
- **Data:** a synthetic corpus ("Demo Motors", model "Velo 125") that the app generates itself

## What's in the pack

| File | Purpose | Who writes it in real SDD |
|---|---|---|
| `.specify/memory/constitution.md` | Project rules: stack, architecture, testing, traceability | Team, once |
| `specs/001-docbot-rag-chatbot/spec.md` | **What and why**: 5 user stories, 35 EARS requirements, success criteria, sample corpus, golden questions | Product / domain owner |
| `specs/001-docbot-rag-chatbot/plan.md` | **How**: architecture, data model, API contract, algorithms, test plan | Agent, reviewed by an engineer |
| `CLAUDE.md` | Claude Code's project memory: reading order, way of working, guardrails | Team |
| `tasks.md`, `traceability.md` | *Not included.* The agent generates them; that is part of the demo. | Agent |

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

### Good moments to pause
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
