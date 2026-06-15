"""配置管理"""

import os
from dataclasses import dataclass, field
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

    # RAG / Chroma Cloud 配置
    # 注意:Cloud 端使用托管嵌入(Qwen dense + Splade sparse + RRF 混合检索),
    # 因此不再需要本地 chroma_dir / embedding_model 字段。
    chroma_host: str = "europe-west1.gcp.trychroma.com"
    chroma_port: int = 443
    chroma_tenant: str = "12e28eb4-2ece-483b-91b5-0cce2b3546e0"
    chroma_database: str = "RAG"
    chroma_api_key: str = ""
    chroma_collection: str = "knowledge_base"
    upload_dir: str = "data/uploads"

    # 分块与检索参数
    chunk_size: int = 500
    chunk_overlap: int = 50
    search_top_k: int = 4  # 表示"最多 K 个不同 source",借 Chroma Cloud GroupBy 实现

    def __post_init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or self.api_key
        self.base_url = os.getenv("DEEPSEEK_BASE_URL") or self.base_url
        self.model = os.getenv("MODEL_NAME") or self.model
        # Chroma Cloud 配置
        self.chroma_host = os.getenv("CHROMA_HOST") or self.chroma_host
        self.chroma_tenant = os.getenv("CHROMA_TENANT") or self.chroma_tenant
        self.chroma_database = os.getenv("CHROMA_DATABASE") or self.chroma_database
        self.chroma_api_key = os.getenv("CHROMA_API_KEY") or self.chroma_api_key
        self.chroma_collection = os.getenv("CHROMA_COLLECTION") or self.chroma_collection
        self.upload_dir = os.getenv("UPLOAD_DIR") or self.upload_dir


settings = Settings()
