"""配置管理"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


@dataclass
class Settings:
    # 小米模型配置
    api_key: str = ""
    base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    model: str = "mimo-v2.5"

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
        self.api_key = os.getenv("MIMO_API_KEY") or self.api_key
        self.chroma_dir = os.getenv("CHROMA_DIR") or self.chroma_dir
        self.upload_dir = os.getenv("UPLOAD_DIR") or self.upload_dir
        self.embedding_model = os.getenv("EMBEDDING_MODEL") or self.embedding_model


settings = Settings()
