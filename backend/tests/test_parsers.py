from reportlab.pdfgen import canvas
from app.services.parsers import parse_pdf

def test_parse_pdf(tmp_path):
    p = tmp_path / "tiny.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(100, 700, "hello rag")
    c.save()
    pages = parse_pdf(str(p))
    assert pages[0]["page"] == 1
    assert "hello rag" in pages[0]["text"]
