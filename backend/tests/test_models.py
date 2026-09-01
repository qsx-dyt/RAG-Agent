from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.entities import Base, Document


def test_document_table_columns():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        d = Document(title="t", source_type="markdown", checksum="abc", status="processing")
        s.add(d)
        s.commit()
        assert d.id is not None
        assert d.tenant_id == "default"
