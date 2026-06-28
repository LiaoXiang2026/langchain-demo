"""配置管理"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

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

    # 本地存储配置
    data_dir: str = "data"
    upload_dir: str = "data/uploads"

    # 嵌入模型配置(HuggingFace)
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"

    # 分块与检索参数
    chunk_size: int = 500
    chunk_overlap: int = 50
    search_top_k: int = 4

    # 聚类参数
    recluster_k_min: int = 5
    recluster_k_max: int = 10

    def __post_init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or self.api_key
        self.base_url = os.getenv("DEEPSEEK_BASE_URL") or self.base_url
        self.model = os.getenv("MODEL_NAME") or self.model
        self.data_dir = os.getenv("DATA_DIR") or self.data_dir
        self.upload_dir = os.getenv("UPLOAD_DIR") or self.upload_dir
        self.embedding_model = os.getenv("EMBEDDING_MODEL") or self.embedding_model


settings = Settings()
