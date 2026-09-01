from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = ""
    llm_model: str = ""

    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024
    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-base"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "rag"
    postgres_password: str = ""
    postgres_db: str = "rag"

    milvus_host: str = "localhost"
    milvus_port: int = 19530
    retrieve_top_k: int = 10
    chunk_size: int = 500
    chunk_overlap: int = 80
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
