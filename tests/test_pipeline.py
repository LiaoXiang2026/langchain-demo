"""文档处理管线测试"""

import os
import tempfile
import shutil
from src.rag.pipeline import DocumentPipeline


def test_ingest_txt_file():
    """测试完整管线：加载→分块→嵌入→存储"""
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = DocumentPipeline(
            persist_dir=tmpdir,
            embedding_model="shibing624/text2vec-base-chinese",
        )
        txt_path = os.path.join(tmpdir, "test.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("这是一段测试内容。" * 50)

        result = pipeline.ingest(txt_path)
        assert result["filename"] == "test.txt"
        assert result["chunk_count"] > 0

        results = pipeline.search("测试内容", k=1)
        assert len(results) > 0
        pipeline._store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
