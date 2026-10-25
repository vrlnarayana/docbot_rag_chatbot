# Ideas (not in SPEC-001; do not build without a spec change)

## Extraction hardening (from the automated security review, 2026-10-25)
- **Page and OCR limits for PDFs** (raised twice by the review, for T013 and T015). A 20 MB PDF can hold thousands of pages, and each page with no text layer is rendered and OCR'd. Consider a maximum page count and a maximum number of OCR pages per document, rejected with a clear 422. Needs agreed numbers in the spec.
- **Layout-mode text amplification.** `pypdf` layout extraction can produce very large strings for pages with extreme coordinates. Consider capping the extracted text per page, or falling back to plain extraction mode above a size limit.
- **Extraction time budget.** One slow upload holds the OCR lock and blocks other uploads. Consider a timeout or a separate worker process for extraction.
- **Open the pdfium document once per extraction**, not once per scanned page.
