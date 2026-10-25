# Ideas (not in SPEC-001; do not build without a spec change)

## Extraction hardening (from the automated security review, 2026-10-25)
- **Page and OCR limits for PDFs** (raised twice by the review, for T013 and T015). A 20 MB PDF can hold thousands of pages, and each page with no text layer is rendered and OCR'd. Consider a maximum page count and a maximum number of OCR pages per document, rejected with a clear 422. Needs agreed numbers in the spec.
- **Layout-mode text amplification.** `pypdf` layout extraction can produce very large strings for pages with extreme coordinates. Consider capping the extracted text per page, or falling back to plain extraction mode above a size limit.
- **Extraction time budget.** One slow upload holds the OCR lock and blocks other uploads. Consider a timeout or a separate worker process for extraction.
- **Open the pdfium document once per extraction**, not once per scanned page.

## Retrieval and answer quality (found while building US-3, 2026-10-25)
- **OCR drops word spaces.** RapidOCR's bundled model (Chinese/English PP-OCR) often merges English words ("Lowbeamwattage"). The samples work around this with wide word gaps, but real scans with normal spacing will index merged tokens, which weakens keyword retrieval and the answerability gate. Options: an English recognition model (needs a one-time download), or splitting merged tokens against a vocabulary.
- **The extractive generator picks the line block with the most question words**, not the block that answers. Prose that repeats the question's terms can beat the table row with the value. An LLM generator (Ollama, OpenAI, Claude) handles this better; a cheap improvement would be to favour blocks containing numbers or units for "what is the value" questions.

## Conversation (found while building FR-070, 2026-10-25)
- **The local follow-up rule cannot substitute words.** Without an LLM, "and the rear one?" after a question about the front disc becomes "…front brake disc? and the rear one?". Retrieval finds the right document, but the extractive quote can still pick the front row. An LLM generator rewrites it properly. A small improvement would be to drop words from the previous question that have a known opposite in the follow-up (front/rear, left/right, low/high, min/max).
