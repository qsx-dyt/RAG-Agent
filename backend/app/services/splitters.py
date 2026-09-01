from typing import Any
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from app.config import get_settings


def split_markdown(text: str) -> list[dict[str, Any]]:
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
    )
    docs = splitter.split_text(text)
    out = []
    for d in docs:
        heading = d.metadata.get("h1") or d.metadata.get("h2") or d.metadata.get("h3") or ""
        out.append({"content": d.page_content, "heading": heading, "metadata": {}})
    return out


def split_text_pages(pages: list[dict]) -> list[dict[str, Any]]:
    s = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    out = []
    for page in pages:
        for piece in splitter.split_text(page["text"]):
            out.append({"content": piece, "heading": None, "metadata": {"page": page["page"]}})
    return out


def parse_and_split(source_type: str, path: str) -> list[dict[str, Any]]:
    if source_type == "pdf":
        from app.services.parsers import parse_pdf
        return split_text_pages(parse_pdf(path))
    if source_type == "markdown":
        from app.services.parsers import parse_markdown
        return split_markdown(parse_markdown(path))
    raise ValueError(f"unsupported source_type: {source_type}")
