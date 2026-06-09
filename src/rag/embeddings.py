"""嵌入模型管理"""

from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings


def get_embeddings(model_name: str = "shibing624/text2vec-base-chinese") -> HuggingFaceEmbeddings:
    """获取 HuggingFace 嵌入模型实例。

    如果 model_name 是本地目录则直接加载，否则从 HF Hub 下载。
    """
    # 如果是本地路径且存在，直接使用
    if Path(model_name).is_dir():
        return HuggingFaceEmbeddings(model_name=model_name)

    # 尝试 HF 缓存目录
    cache_path = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{model_name.replace('/', '--')}"
    if cache_path.is_dir():
        return HuggingFaceEmbeddings(model_name=str(cache_path))

    return HuggingFaceEmbeddings(model_name=model_name)
