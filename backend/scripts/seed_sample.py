import sys
from pathlib import Path
from app.core.db import SessionLocal, init_db
from app.core.milvus import get_milvus_client
from app.services import ingestion

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_data"


def main() -> None:
    init_db()
    get_milvus_client().ensure_collection()
    db = SessionLocal()
    try:
        for path in sorted(SAMPLE_DIR.iterdir()):
            if path.suffix.lower() == ".pdf":
                st = "pdf"
            elif path.suffix.lower() in (".md", ".markdown"):
                st = "markdown"
            else:
                continue
            doc = ingestion.ingest_bytes(db, path.name, path.read_bytes(), st)
            print(f"{doc.title}: {doc.status}")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
