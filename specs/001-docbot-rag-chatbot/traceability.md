# Traceability: SPEC-001

Every functional requirement maps to the tasks that implement it, the source files, and the tests that prove it (Constitution I.5). A row with no test is a gap and blocks "done".

| FR | Tasks | Source files | Tests | Status |
|---|---|---|---|---|
| FR-001 | T005 | `app/core/errors.py` | `tests/unit/test_errors.py::test_fr_001_supported_extensions` | partial |
| FR-002 | T005 | `app/core/errors.py` | `tests/unit/test_errors.py::test_fr_002_unsupported_type_message_lists_supported_types` | partial |
| FR-003 | | | | gap |
| FR-004 | | | | gap |
| FR-005 | | | | gap |
| FR-006 | | | | gap |
| FR-007 | | | | gap |
| FR-008 | | | | gap |
| FR-009 | | | | gap |
| FR-010 | T004 | `app/core/models.py` | `tests/unit/test_models.py::test_fr_010_ask_request_rejects_bad_question_length`, `tests/unit/test_models.py::test_fr_010_ask_request_top_k_bounds`, `tests/unit/test_settings.py::test_fr_010_top_k_bounds` | partial |
| FR-011 | | | | gap |
| FR-012 | | | | gap |
| FR-013 | | | | gap |
| FR-014 | T004 | `app/core/models.py` | `tests/unit/test_models.py::test_fr_014_citation_out_fields` | partial |
| FR-015 | | | | gap |
| FR-016 | | | | gap |
| FR-017 | | | | gap |
| FR-018 | | | | gap |
| FR-020 | T004 | `app/core/models.py` | `tests/unit/test_models.py::test_fr_020_document_out_has_listing_fields_and_no_internal_ones` | partial |
| FR-021 | T004 | `app/core/models.py` | `tests/unit/test_models.py::test_fr_021_chunk_out_fields` | partial |
| FR-022 | | | | gap |
| FR-023 | | | | gap |
| FR-030 | | | | gap |
| FR-031 | | | | gap |
| FR-032 | | | | gap |
| FR-040 | | | | gap |
| FR-041 | | | | gap |
| FR-050 | T001, T002 | `pyproject.toml`, `.env.example`, `app/settings.py` | `tests/unit/test_settings.py::test_fr_050_defaults_match_plan`, `tests/unit/test_settings.py::test_fr_050_reads_env_and_dotenv` | tested |
| FR-051 | | | | gap |
| FR-052 | T002 | `app/settings.py` | `tests/unit/test_settings.py::test_fr_052_unknown_generator_fails_with_valid_options`, `tests/unit/test_settings.py::test_fr_052_unknown_retriever_fails_with_valid_options` | partial (startup wiring in T009) |
| FR-060 | | | | gap |
| FR-061 | | | | gap |
| FR-062 | | | | gap |
| FR-063 | | | | gap |
| FR-064 | | | | gap |

## Constitution and non-functional checks

| Rule | Tasks | Source files | Tests |
|---|---|---|---|
| VII.3 structured request logs, no document text | T003 | `app/api/logging.py` | `tests/api/test_logging.py::test_one_structured_line_per_request` |
