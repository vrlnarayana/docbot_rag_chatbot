# Traceability: SPEC-001

Every functional requirement maps to the tasks that implement it, the source files, and the tests that prove it (Constitution I.5). A row with no test is a gap and blocks "done".

| FR | Tasks | Source files | Tests | Status |
|---|---|---|---|---|
| FR-001 | T005, T013, T014 | `app/core/errors.py`, `app/adapters/extractors.py`, `app/core/services.py` | `tests/unit/test_errors.py::test_fr_001_supported_extensions`, `tests/unit/test_extract_pdf.py::test_fr_001_text_pdf_pages`, `tests/unit/test_extract_pdf.py::test_fr_001_table_rows_stay_on_one_line`, `tests/unit/test_ingestion.py::test_fr_001_ingest_indexes_document_and_chunks` | partial |
| FR-002 | T005, T014 | `app/core/errors.py`, `app/core/services.py` | `tests/unit/test_errors.py::test_fr_002_unsupported_type_message_lists_supported_types`, `tests/unit/test_ingestion.py::test_fr_002_unsupported_type_stores_nothing` | partial |
| FR-003 | T014 | `app/core/services.py` | `tests/unit/test_ingestion.py::test_fr_003_too_large_is_rejected` | partial |
| FR-004 | T013 | `app/adapters/extractors.py` | `tests/unit/test_extract_pdf.py::test_fr_004_page_without_text_layer_is_ocrd` | tested |
| FR-005 | T012 | `app/adapters/extractors.py` | `tests/unit/test_extract_image.py::test_fr_005_png_text_is_ocr_page_one`, `tests/unit/test_extract_image.py::test_fr_005_jpg_supported` | tested |
| FR-006 | T011 | `app/adapters/extractors.py` | `tests/unit/test_extract_text.py::test_fr_006_utf8_text_is_page_one`, `tests/unit/test_extract_text.py::test_fr_006_falls_back_to_latin1` | tested |
| FR-007 | T010 | `app/core/chunking.py` | `tests/unit/test_chunking.py::test_fr_007_chunks_never_exceed_size`, `tests/unit/test_chunking.py::test_fr_007_consecutive_chunks_overlap`, `tests/unit/test_chunking.py::test_fr_007_prefers_paragraph_breaks`, `tests/unit/test_chunking.py::test_fr_007_prefers_line_breaks_over_spaces`, `tests/unit/test_chunking.py::test_fr_007_never_crosses_pages_and_keeps_source`, `tests/unit/test_chunking.py::test_fr_007_drops_tiny_chunks_unless_only_text`, `tests/unit/test_chunking.py::test_fr_007_no_text_is_lost`, `tests/unit/test_chunking.py::test_fr_007_short_text_is_one_chunk` | tested |
| FR-008 | T007, T014 | `app/adapters/db.py`, `app/core/services.py` | `tests/unit/test_db.py::test_fr_008_lookup_by_sha256`, `tests/unit/test_ingestion.py::test_fr_008_duplicate_returns_existing_without_reindexing` | partial |
| FR-009 | T007, T014 | `app/adapters/db.py`, `app/core/services.py` | `tests/unit/test_db.py::test_fr_009_failed_insert_stores_nothing`, `tests/unit/test_ingestion.py::test_fr_009_no_text_stores_nothing`, `tests/unit/test_ingestion.py::test_fr_009_failed_insert_removes_saved_file` | partial |
| FR-010 | T004 | `app/core/models.py` | `tests/unit/test_models.py::test_fr_010_ask_request_rejects_bad_question_length`, `tests/unit/test_models.py::test_fr_010_ask_request_top_k_bounds`, `tests/unit/test_settings.py::test_fr_010_top_k_bounds` | partial |
| FR-011 | | | | gap |
| FR-012 | | | | gap |
| FR-013 | | | | gap |
| FR-014 | T004 | `app/core/models.py` | `tests/unit/test_models.py::test_fr_014_citation_out_fields` | partial |
| FR-015 | | | | gap |
| FR-016 | | | | gap |
| FR-017 | | | | gap |
| FR-018 | | | | gap |
| FR-020 | T004, T007 | `app/core/models.py`, `app/adapters/db.py` | `tests/unit/test_models.py::test_fr_020_document_out_has_listing_fields_and_no_internal_ones`, `tests/unit/test_db.py::test_fr_020_add_get_and_list` | partial |
| FR-021 | T004, T007 | `app/core/models.py`, `app/adapters/db.py` | `tests/unit/test_models.py::test_fr_021_chunk_out_fields`, `tests/unit/test_db.py::test_fr_021_chunks_in_page_order` | partial |
| FR-022 | T007, T008 | `app/adapters/db.py`, `app/adapters/file_store.py` | `tests/unit/test_db.py::test_fr_022_delete_removes_document_and_chunks`, `tests/unit/test_file_store.py::test_fr_022_delete_removes_file` | partial |
| FR-023 | | | | gap |
| FR-030 | | | | gap |
| FR-031 | | | | gap |
| FR-032 | | | | gap |
| FR-040 | | | | gap |
| FR-041 | | | | gap |
| FR-050 | T001, T002 | `pyproject.toml`, `.env.example`, `app/settings.py` | `tests/unit/test_settings.py::test_fr_050_defaults_match_plan`, `tests/unit/test_settings.py::test_fr_050_reads_env_and_dotenv` | tested |
| FR-051 | T009 | `app/api/routes/status.py`, `app/api/deps.py` | `tests/api/test_health_status.py::test_fr_051_status_reports_configuration_and_counts` | partial (fallbacks in T017) |
| FR-052 | T002, T009 | `app/settings.py`, `app/api/main.py` | `tests/unit/test_settings.py::test_fr_052_unknown_generator_fails_with_valid_options`, `tests/unit/test_settings.py::test_fr_052_unknown_retriever_fails_with_valid_options`, `tests/api/test_health_status.py::test_fr_052_startup_fails_with_clear_message` | tested |
| FR-060 | | | | gap |
| FR-061 | | | | gap |
| FR-062 | | | | gap |
| FR-063 | | | | gap |
| FR-064 | | | | gap |

## Constitution and non-functional checks

| Rule | Tasks | Source files | Tests |
|---|---|---|---|
| VII.3 structured request logs, no document text | T003 | `app/api/logging.py` | `tests/api/test_logging.py::test_one_structured_line_per_request` |
| III.10 `app/core` imports no infrastructure libraries | T006 | `app/core/` | `tests/unit/test_architecture.py::test_core_imports_no_banned_modules`, `::test_core_does_not_import_adapters_or_api` |
| IV.3 uploads stored under generated names, never user names | T008 | `app/adapters/file_store.py` | `tests/unit/test_file_store.py::test_saves_under_generated_name_inside_folder`, `::test_rejects_unsafe_extensions`, `::test_delete_refuses_names_outside_folder` |
| NFR-006 no paths or stack traces in responses | T009 | `app/api/errors.py` | `tests/api/test_health_status.py::test_nfr_006_unexpected_errors_hide_details`, `::test_domain_errors_become_error_response`, `::test_validation_errors_use_error_shape` |
| Image decoding limited to PNG/JPEG and bounded size (security review) | T012 | `app/adapters/extractors.py` | `tests/unit/test_extract_safety.py` |
