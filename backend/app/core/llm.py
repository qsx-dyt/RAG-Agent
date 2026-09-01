from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.config import get_settings


def get_llm() -> ChatOpenAI:
    s = get_settings()
    return ChatOpenAI(model=s.llm_model, api_key=s.openai_api_key or "EMPTY",
                      base_url=s.openai_base_url or None, temperature=0.2,
                      timeout=60, max_retries=1)


def get_embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    return OpenAIEmbeddings(model=s.embedding_model, api_key=s.embedding_api_key or "EMPTY",
                            base_url=s.embedding_base_url or None)


def embed_texts(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    embeddings = get_embeddings()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        out.extend(embeddings.embed_documents(batch))
    return out
