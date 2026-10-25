"""Show untrusted text (documents, file names, LLM output) as text, never as live Markdown."""


def plain(text: str) -> str:
    """Document or LLM text as written: no headings, tables, links or images; keep line breaks."""
    for char in "\\`*_#|[]<>":
        text = text.replace(char, "\\" + char)
    return text.replace("\n", "  \n")


def inline(text: str) -> str:
    """Short labels such as file names: no links, images or HTML, but underscores stay readable."""
    for char in "\\`[]<>":
        text = text.replace(char, "\\" + char)
    return text
