"""配置管理"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


@dataclass
class Settings:
    # LLM 配置(DeepSeek,OpenAI 兼容接口)
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"

    # Agent 配置
    temperature: float = 0.7
    max_tokens: int = 2048

    # RAG 配置
    chroma_dir: str = "data/chroma_db"
    upload_dir: str = "data/uploads"
    embedding_model: str = "shibing624/text2vec-base-chinese"
    chunk_size: int = 500
    chunk_overlap: int = 50
    search_top_k: int = 4

    def __post_init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or self.api_key
        self.base_url = os.getenv("DEEPSEEK_BASE_URL") or self.base_url
        self.model = os.getenv("MODEL_NAME") or self.model
        self.chroma_dir = os.getenv("CHROMA_DIR") or self.chroma_dir
        self.upload_dir = os.getenv("UPLOAD_DIR") or self.upload_dir
        self.embedding_model = os.getenv("EMBEDDING_MODEL") or self.embedding_model


settings = Settings()
