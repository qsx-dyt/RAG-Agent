from pathlib import Path
import pdfplumber


def parse_pdf(path: str) -> list[dict]:
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"text": text, "page": i})
    return pages


def parse_markdown(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
