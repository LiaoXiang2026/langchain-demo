"""嵌入模型管理"""

from langchain_huggingface import HuggingFaceEmbeddings


def get_embeddings(model_name: str = "shibing624/text2vec-base-chinese") -> HuggingFaceEmbeddings:
    """获取 HuggingFace 嵌入模型实例。首次调用时会自动下载模型（约 100MB）。"""
    return HuggingFaceEmbeddings(model_name=model_name)
