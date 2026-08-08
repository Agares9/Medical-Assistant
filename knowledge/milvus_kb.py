"""
医学知识库（Milvus）

功能：
1. 文档向量化和存储
2. 语义检索
3. 知识库管理

参考实现：/Users/saintgeo/Desktop/self-learn/shanglv
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GLOG_minloglevel", "2")

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer


def _model_cache_roots() -> List[Path]:
    roots: List[Path] = []
    env_values = [
        os.getenv("SENTENCE_TRANSFORMERS_HOME", ""),
        os.getenv("HUGGINGFACE_HUB_CACHE", ""),
        os.getenv("HF_HOME", ""),
    ]
    for value in env_values:
        if value:
            roots.append(Path(value))

    roots.append(Path.home() / ".cache" / "huggingface")
    roots.append(Path.home() / ".cache" / "sentence_transformers")
    return roots


def _find_local_embedding_model(embedding_model: str) -> Optional[str]:
    model_name = embedding_model.replace("/", "--")
    candidates = []
    for root in _model_cache_roots():
        candidates.extend([
            root / "hub" / f"models--{model_name}" / "snapshots",
            root / f"models--{model_name}" / "snapshots",
            root / model_name / "snapshots",
        ])

    for snapshots_root in candidates:
        if snapshots_root.exists():
            snapshots = sorted(
                [item for item in snapshots_root.iterdir() if item.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if snapshots:
                return str(snapshots[0])
    return None


class MedicalKnowledgeBase:
    """医学知识库"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        db_path: str = "./knowledge/data/milvus_lite.db",
        collection_name: str = "medical_knowledge",
        embedding_model: str = "BAAI/bge-small-zh-v1.5"
    ):
        """
        初始化医学知识库

        Args:
            db_path: Milvus Lite 数据库文件路径
            collection_name: Collection 名称
            embedding_model: Embedding 模型名称或本地路径
        """
        # 防止重复初始化
        if hasattr(self, '_initialized'):
            return

        self.db_path = db_path
        self.collection_name = collection_name

        # 确保数据目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 初始化 Embedding 模型（支持本地缓存路径）
        model_path = _find_local_embedding_model(embedding_model)
        if model_path:
            logger.info(f"Loading embedding model from local cache: {model_path}")
            self.embedding_model = SentenceTransformer(model_path, device='cpu')
        else:
            logger.info(f"Loading embedding model: {embedding_model}")
            self.embedding_model = SentenceTransformer(embedding_model, device='cpu')

        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded (dimension={self.embedding_dim})")

        # 初始化 Milvus Lite
        logger.info(f"Connecting to Milvus Lite: {db_path}")
        self.milvus_client = MilvusClient(db_path, keep_alive=False)

        # 创建 collection（如果不存在）
        if not self.milvus_client.has_collection(collection_name):
            logger.info(f"Creating collection: {collection_name}")
            self.milvus_client.create_collection(
                collection_name=collection_name,
                dimension=self.embedding_dim,
                metric_type="COSINE",  # 余弦相似度
                auto_id=True  # 自动生成整数ID
            )
        else:
            logger.info(f"Collection already exists: {collection_name}")

        self._ensure_collection_loaded()
        self._initialized = True

    def _ensure_collection_loaded(self):
        """确保 collection 已加载，避免 released 状态下搜索失败。"""
        try:
            self.milvus_client.load_collection(collection_name=self.collection_name)
            logger.debug(f"Collection loaded: {self.collection_name}")
        except Exception as e:
            message = str(e).lower()
            already_loaded = "already" in message and "load" in message
            if already_loaded:
                logger.debug(f"Collection already loaded: {self.collection_name}")
            else:
                logger.warning(f"Failed to load collection {self.collection_name}: {e}")

    def _chunk_text(self, text: str, chunk_size: int = 1024, overlap: int = 100) -> List[str]:
        """
        分块文本

        Args:
            text: 原始文本
            chunk_size: 块大小（字符数）
            overlap: 重叠字符数

        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap  # 重叠

        return chunks

    def add_documents(self, documents: List[Dict[str, Any]], chunk_size: int = 1024) -> int:
        """
        添加文档到知识库（支持分块）

        Args:
            documents: 文档列表，每个文档包含 id, content, metadata
            chunk_size: 分块大小（字符数），默认 1024

        Returns:
            成功添加的文档块数量
        """
        if not documents:
            logger.warning("No documents to add")
            return 0

        logger.info(f"Adding {len(documents)} documents to knowledge base (chunk_size={chunk_size})...")

        # 分块并向量化
        all_chunks = []
        for doc in documents:
            chunks = self._chunk_text(doc["content"], chunk_size=chunk_size)
            for i, chunk in enumerate(chunks):
                metadata = doc.get("metadata", {}).copy()
                metadata["doc_id"] = doc["id"]
                metadata["chunk_id"] = i
                metadata["total_chunks"] = len(chunks)

                all_chunks.append({
                    "content": chunk,
                    "metadata": metadata
                })

        logger.info(f"Split into {len(all_chunks)} chunks")

        # 向量化
        contents = [chunk["content"] for chunk in all_chunks]
        vectors = self.embedding_model.encode(contents, show_progress_bar=True)

        # 准备数据
        data = []
        for i, chunk in enumerate(all_chunks):
            data.append({
                "vector": vectors[i].tolist(),
                "content": chunk["content"],
                "metadata": json.dumps(chunk["metadata"], ensure_ascii=False)
            })

        # 插入
        self.milvus_client.insert(self.collection_name, data)
        logger.info(f"Successfully added {len(data)} chunks")

        return len(data)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 返回top K个结果
            filter_type: 可选的类型过滤（如 "lifestyle", "disease_classification"）

        Returns:
            文档列表，每个文档包含 id, content, metadata, score
        """
        logger.debug(f"Searching for: {query} (top_k={top_k}, filter_type={filter_type})")

        # 向量化查询
        query_vector = self.embedding_model.encode([query])[0]

        # 构建过滤条件
        filter_expr = None
        if filter_type:
            filter_expr = f'metadata like "%\\"type\\": \\"{filter_type}\\"%"'

        # 检索。Milvus Lite 重启后已有 collection 可能处于 released 状态，需要 load 后重试。
        try:
            results = self.milvus_client.search(
                collection_name=self.collection_name,
                data=[query_vector.tolist()],
                limit=top_k,
                filter=filter_expr,
                output_fields=["content", "metadata"]
            )
        except Exception as e:
            message = str(e)
            if "released" in message or "load() before" in message:
                logger.warning(f"Collection is not loaded, loading and retrying search: {self.collection_name}")
                self._ensure_collection_loaded()
                try:
                    results = self.milvus_client.search(
                        collection_name=self.collection_name,
                        data=[query_vector.tolist()],
                        limit=top_k,
                        filter=filter_expr,
                        output_fields=["content", "metadata"]
                    )
                except Exception as retry_error:
                    logger.error(f"Search failed after loading collection: {retry_error}")
                    return []
            else:
                logger.error(f"Search failed: {e}")
                return []

        # 格式化结果
        documents = []
        for hits in results:
            for hit in hits:
                try:
                    documents.append({
                        "id": hit["id"],
                        "content": hit["entity"]["content"],
                        "metadata": json.loads(hit["entity"]["metadata"]),
                        "score": 1 - hit["distance"]  # 转换为相似度分数
                    })
                except Exception as e:
                    logger.warning(f"Failed to parse result: {e}")
                    continue

        logger.debug(f"Found {len(documents)} documents")
        return documents

    def delete_collection(self):
        """删除 collection（用于测试）"""
        if self.milvus_client.has_collection(self.collection_name):
            self.milvus_client.drop_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")

    def count_documents(self) -> int:
        """统计文档数量"""
        try:
            stats = self.milvus_client.describe_collection(self.collection_name)
            # Note: Milvus Lite may not return accurate count, this is a best-effort
            return stats.get("num_entities", 0)
        except Exception as e:
            logger.warning(f"Failed to count documents: {e}")
            return 0
