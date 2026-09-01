from pathlib import Path

def test_sample_data_exists():
    root = Path(__file__).resolve().parents[2]
    files = list((root / "sample_data").glob("*"))
    md = [f for f in files if f.suffix in (".md", ".markdown")]
    pdf = [f for f in files if f.suffix == ".pdf"]
    assert len(md) >= 6
    assert len(pdf) >= 2
