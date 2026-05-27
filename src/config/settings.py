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

    def __post_init__(self):
        self.api_key = os.getenv("MIMO_API_KEY") or self.api_key


settings = Settings()
