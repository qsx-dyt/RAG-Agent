from app.services.splitters import split_markdown, split_text_pages

def test_markdown_header_split():
    md = "# 报销制度\n差旅费报销需要发票。\n## 审批流程\n需财务审核。"
    chunks = split_markdown(md)
    assert any(c["heading"] == "报销制度" for c in chunks)

def test_pdf_pages_keep_page_number():
    pages = [{"text": "第一页内容" * 200, "page": 1},
             {"text": "第二页内容" * 200, "page": 2}]
    chunks = split_text_pages(pages)
    assert chunks[0]["metadata"]["page"] in (1, 2)
    assert len(chunks) > 2
