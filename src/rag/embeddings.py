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

    # 尝试 HF 缓存目录:hub/models--xxx/snapshots/<rev>/ 才是含 config.json 的真实模型目录,
    # 外层 hub/models--xxx/ 只有 blobs/ 和 snapshots/ 子目录,直接传给 sentence-transformers 会报
    # "Unrecognized model"。
    hub_root = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{model_name.replace('/', '--')}"
    snapshots_dir = hub_root / "snapshots"
    if snapshots_dir.is_dir():
        revs = [p for p in snapshots_dir.iterdir() if p.is_dir()]
        if revs:
            return HuggingFaceEmbeddings(model_name=str(revs[0]))

    return HuggingFaceEmbeddings(model_name=model_name)
