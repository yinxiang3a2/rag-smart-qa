"""
向量存储服务
基于 FAISS 实现，提供高性能向量检索
支持 BM25F + FAISS + RRF 混合检索
"""
import os
import json
import shutil
import logging
import threading
import math
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import faiss
import numpy as np

from .embedding_service import embedding_service
from ..config import settings

logger = logging.getLogger(__name__)

# BM25F 参数
BM25F_K1 = 1.5
BM25F_B = 0.75
BM25F_FIELD_WEIGHTS = {
    "content": 1.0,  # chunk内容
    "filename": 0.5, # 文件名权重较低
}

# RRF 参数
RRF_K = 60


class VectorStore:
    """
    基于 FAISS 的向量存储
    使用 IndexFlatIP + L2 归一化向量实现余弦相似度检索
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._index: Optional[faiss.Index] = None
        self._dimension: int = settings.EMBEDDING_DIMENSION

        # 持久化文件路径
        self._index_path = settings.VECTOR_DB_DIR / "faiss.index"
        self._meta_path = settings.VECTOR_DB_DIR / "metadata.json"

        # 元数据
        # _chunk_meta[i] = {doc_id, chunk_id, content, created_at}  对应 FAISS 第 i 行
        self._chunk_meta: List[dict] = []
        # _doc_to_indices[doc_id] = [index1, index2, ...]           doc 包含的 FAISS 行号
        self._doc_to_indices: Dict[str, List[int]] = {}
        # _doc_meta[doc_id] = {...}                                doc 元数据
        self._doc_meta: Dict[str, dict] = {}
        # 已删除的 doc_id（软删除，避免重建索引开销）
        self._deleted_docs: set = set()

        # 确保目录存在
        settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)

        # 尝试从磁盘加载已有索引
        self._load_from_disk()

        logger.info(f"向量存储已初始化（FAISS模式），维度={self._dimension}，索引路径={self._index_path}")

    def _load_from_disk(self):
        """从磁盘加载 FAISS 索引和元数据"""
        if not self._index_path.exists() or not self._meta_path.exists():
            logger.info("未找到持久化文件，将从头创建新索引")
            self._init_index()
            return

        try:
            self._index = faiss.read_index(str(self._index_path))
            with open(self._meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self._chunk_meta = meta.get("chunk_meta", [])
            self._doc_to_indices = meta.get("doc_to_indices", {})
            self._doc_meta = meta.get("doc_meta", {})
            self._deleted_docs = set(meta.get("deleted_docs", []))
            logger.info(f"从磁盘加载索引成功: {self._index.ntotal} 条向量, {len(self._doc_meta)} 个文档")
        except Exception as e:
            logger.warning(f"加载索引失败: {e}，将重新创建")
            self._init_index()

    def _init_index(self):
        """初始化空的 FAISS 索引"""
        # Inner Product (即余弦相似度，向量已 L2 归一化)
        self._index = faiss.IndexFlatIP(self._dimension)

    def _normalize(self, vectors: List[List[float]]) -> np.ndarray:
        """L2 归一化向量，使点积等价于余弦相似度"""
        arr = np.array(vectors, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # 避免除零
        return arr / norms

    def _save_to_disk(self):
        """持久化索引和元数据到磁盘"""
        try:
            faiss.write_index(self._index, str(self._index_path))
            meta = {
                "chunk_meta": self._chunk_meta,
                "doc_to_indices": self._doc_to_indices,
                "doc_meta": self._doc_meta,
                "deleted_docs": list(self._deleted_docs),
            }
            with open(self._meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False)
            logger.info(f"索引已持久化: {self._index.ntotal} 向量")
        except Exception as e:
            logger.error(f"持久化索引失败: {e}")

    def add_document(
        self,
        doc_id: str,
        chunks: List[str],
        metadata: Optional[dict] = None
    ) -> int:
        """
        添加文档到向量存储（线程安全）
        Args:
            doc_id: 文档ID
            chunks: 文本块列表
            metadata: 文档元数据
        Returns:
            添加的文本块数量
        """
        if not chunks:
            return 0

        # 生成并归一化向量
        vectors = embedding_service.embed_texts(chunks)
        normalized = self._normalize(vectors)

        with self._lock:
            # 记录当前 FAISS 中已有向量数，作为起始偏移
            start_idx = self._index.ntotal

            # 添加到 FAISS 索引
            self._index.add(normalized)

            # 记录 chunk 元数据
            now = datetime.now().isoformat()
            for i, chunk in enumerate(chunks):
                chunk_info = {
                    "chunk_id": f"{doc_id}_chunk_{i}",
                    "doc_id": doc_id,
                    "content": chunk,
                    "created_at": now,
                }
                self._chunk_meta.append(chunk_info)

            # 记录 doc -> indices 映射
            indices = list(range(start_idx, start_idx + len(chunks)))
            self._doc_to_indices[doc_id] = indices
            self._doc_meta[doc_id] = metadata or {}
            if doc_id in self._deleted_docs:
                self._deleted_docs.discard(doc_id)

            # 持久化
            self._save_to_disk()

        logger.info(f"文档 {doc_id} 已索引，共 {len(chunks)} 个文本块")
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[dict] = None
    ) -> List[dict]:
        """
        检索相关文档块（线程安全）
        Args:
            query: 查询文本
            top_k: 返回数量
            filters: 过滤条件
        Returns:
            相关文档块列表 [{"doc_id", "chunk_id", "content", "score", "metadata"}, ...]
        """
        if top_k is None:
            top_k = settings.RAG_TOP_K

        # 生成并归一化查询向量
        query_vector = embedding_service.embed_text(query)
        query_normalized = self._normalize([query_vector])

        logger.info(f"FAISS 向量检索，查询: {query[:50]}...")

        with self._lock:
            if self._index.ntotal == 0:
                return []

            # FAISS 搜索（返回 top_k * 2，便于后续过滤已删除文档）
            k_search = min(top_k * 4, self._index.ntotal)
            scores, indices = self._index.search(query_normalized, k_search)

            results = []
            seen_docs = {}  # doc_id -> 该文档已返回的chunk数量

            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                if idx >= len(self._chunk_meta):
                    continue

                chunk_info = self._chunk_meta[idx]
                doc_id = chunk_info["doc_id"]

                # 跳过已删除文档
                if doc_id in self._deleted_docs:
                    continue

                # 过滤条件
                if filters and doc_id not in filters.get("doc_ids", []):
                    continue

                # 阈值过滤
                if score < settings.RAG_SIMILARITY_THRESHOLD:
                    continue

                # 每个 doc 最多返回 2 个 chunk（避免信息丢失）
                doc_chunk_count = seen_docs.get(doc_id, 0)
                if doc_chunk_count >= 2:
                    continue
                seen_docs[doc_id] = doc_chunk_count + 1

                results.append({
                    "doc_id": doc_id,
                    "chunk_id": chunk_info["chunk_id"],
                    "content": chunk_info["content"],
                    "score": float(score),
                    "metadata": self._doc_meta.get(doc_id, {}),
                })

                if len(results) >= top_k:
                    break

        return results

    def _tokenize_chinese(self, text: str) -> List[str]:
        """中文分词（过滤空字符和单字符）"""
        try:
            import jieba
            tokens = list(jieba.cut(text))
            # 过滤空字符、空格和单字符（除了数字）
            return [t.strip() for t in tokens if t.strip() and len(t.strip()) >= 1 and not t.strip().isspace()]
        except ImportError:
            # 降级：按非中文字符分割
            return [t for t in re.split(r'[^\u4e00-\u9fff\w]+', text) if t]

    def _bm25f_search(self, query: str, top_k: int = 10) -> List[dict]:
        """
        BM25F检索文档
        """
        with self._lock:
            if not self._chunk_meta:
                return []

            query_tokens = self._tokenize_chinese(query)
            if not query_tokens:
                return []

            # 构建倒排索引（保存chunk引用避免索引错位）
            doc_count = len(self._chunk_meta)
            doc_freq = {}  # term -> 文档频率
            doc_term_freq = []  # [ (chunk, {term: tf, ...}), ... ]
            doc_field_lens = []  # 每个chunk的字段长度

            for chunk in self._chunk_meta:
                # 跳过已删除文档
                if chunk["doc_id"] in self._deleted_docs:
                    continue

                content = chunk.get("content", "")
                filename = chunk.get("metadata", {}).get("filename", "")

                tokens = self._tokenize_chinese(content)
                filename_tokens = self._tokenize_chinese(filename)

                # 计算词频
                tf = {}
                for t in tokens:
                    tf[t] = tf.get(t, 0) + 1
                for t in filename_tokens:
                    tf[t] = tf.get(t, 0) + 0.5  # 文件名权重减半

                doc_term_freq.append((chunk, tf))
                doc_field_lens.append(len(tokens))

                # 统计文档频率
                for t in set(tokens):
                    doc_freq[t] = doc_freq.get(t, 0) + 1

            if not doc_term_freq:
                return []

            # 计算平均长度
            avg_len = sum(doc_field_lens) / len(doc_field_lens) if doc_field_lens else 1

            # 计算每个文档的BM25F得分
            scores = []
            for i, (chunk, tf) in enumerate(doc_term_freq):
                score = 0.0
                doc_len = doc_field_lens[i]
                len_norm = doc_len / avg_len if avg_len > 0 else 1

                for term in query_tokens:
                    if term in tf:
                        # IDF
                        df = doc_freq.get(term, 1)
                        idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1)

                        # TF with field weight
                        weighted_tf = tf[term]

                        # BM25F formula
                        numerator = weighted_tf * (BM25F_K1 + 1)
                        denominator = weighted_tf + BM25F_K1 * (1 - BM25F_B + BM25F_B * len_norm)

                        score += idf * numerator / denominator if denominator > 0 else 0

                if score > 0:
                    scores.append((i, score, chunk))

            # 排序并去重
            scores.sort(key=lambda x: x[1], reverse=True)

            results = []
            seen_docs = set()
            for idx, score, chunk in scores:
                doc_id = chunk["doc_id"]
                if doc_id in seen_docs:
                    continue
                seen_docs.add(doc_id)
                results.append({
                    "doc_id": doc_id,
                    "chunk_id": chunk["chunk_id"],
                    "content": chunk["content"],
                    "score": float(score),
                    "bm25f_score": float(score),
                    "metadata": self._doc_meta.get(doc_id, {}),
                })
                if len(results) >= top_k:
                    break

            return results

    def _rrf_fusion(self, ranked_lists: List[List[Tuple]], k: int = 60) -> List[Tuple]:
        """
        RRF (Reciprocal Rank Fusion) 融合多个排序结果
        优先保留有content的数据
        """
        rrf_scores = {}

        for ranked_list in ranked_lists:
            for rank, item in enumerate(ranked_list, 1):
                if isinstance(item, dict):
                    doc_id = item.get("doc_id")
                else:
                    doc_id = item[0] if len(item) > 0 else None

                if doc_id is None:
                    continue

                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = {"rrf": 0.0, "data": None, "has_content": False}
                rrf_scores[doc_id]["rrf"] += 1.0 / (k + rank)
                
                # 优先保存有content的数据
                if isinstance(item, dict):
                    if not rrf_scores[doc_id]["has_content"] or item.get("content"):
                        rrf_scores[doc_id]["data"] = item
                        if item.get("content"):
                            rrf_scores[doc_id]["has_content"] = True

        # 按RRF得分排序
        fused = [(doc_id, info["rrf"], info["data"]) for doc_id, info in rrf_scores.items()]
        fused.sort(key=lambda x: x[1], reverse=True)
        return fused

    def hybrid_search(self, query: str, top_k: int = 5, use_bm25f: bool = True) -> List[dict]:
        """
        BM25F + FAISS + RRF 混合检索
        策略：
        1. RRF融合去重（按doc_id）
        2. 优先选取两个检索都命中的文档（双命中优先）
        3. 最终取top_k的60%（向量优先配额）
        """
        # 1. 向量检索
        vector_results = self.search(query, top_k=top_k * 2)
        vector_doc_chunks = {}  # doc_id -> best_chunk
        for r in vector_results:
            doc_id = r["doc_id"]
            if doc_id not in vector_doc_chunks:
                vector_doc_chunks[doc_id] = r

        # 2. BM25F检索
        bm25f_doc_chunks = {}
        if use_bm25f:
            bm25f_results = self._bm25f_search(query, top_k=top_k * 2)
            for r in bm25f_results:
                doc_id = r["doc_id"]
                if doc_id not in bm25f_doc_chunks:
                    bm25f_doc_chunks[doc_id] = r

        # 3. RRF融合（doc_id级别）
        all_doc_ids = set(vector_doc_chunks.keys()) | set(bm25f_doc_chunks.keys())
        rrf_scores = {}
        for doc_id in all_doc_ids:
            score = 0.0
            # 向量排名得分
            if doc_id in vector_doc_chunks:
                v_rank = list(vector_doc_chunks.keys()).index(doc_id) + 1
                score += 1.0 / (RRF_K + v_rank)
            # BM25F排名得分
            if doc_id in bm25f_doc_chunks:
                b_rank = list(bm25f_doc_chunks.keys()).index(doc_id) + 1
                score += 1.0 / (RRF_K + b_rank)
            rrf_scores[doc_id] = score

        # 按RRF得分排序
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # 4. 取top_k的60%，双命中优先，其余按RRF排名
        quota = max(1, int(top_k * 0.6 + 0.5))
        selected_docs = sorted_docs[:quota]

        # 分离双命中和单命中
        double_hit = []
        single_hit = []
        for doc_id, rrf_score in selected_docs:
            if doc_id in vector_doc_chunks and doc_id in bm25f_doc_chunks:
                double_hit.append((doc_id, rrf_score))
            else:
                single_hit.append((doc_id, rrf_score))

        # 双命中放前面，其余按RRF排名接着放
        ordered_docs = double_hit + single_hit

        # 5. 构建最终结果
        results = []
        seen_chunks = set()
        for doc_id, rrf_score in ordered_docs:
            # 优先取向量检索的chunk
            if doc_id in vector_doc_chunks:
                chunk = vector_doc_chunks[doc_id].copy()
            else:
                chunk = bm25f_doc_chunks[doc_id].copy()

            chunk["rrf_score"] = rrf_score
            chunk["vector_score"] = vector_doc_chunks.get(doc_id, {}).get("score", 0)
            chunk["bm25f_score"] = bm25f_doc_chunks.get(doc_id, {}).get("score", 0)

            # 如果是双命中且BM25F的chunk不同，额外保留BM25F的chunk
            if doc_id in vector_doc_chunks and doc_id in bm25f_doc_chunks:
                v_chunk_id = vector_doc_chunks[doc_id].get("chunk_id", doc_id)
                b_chunk_id = bm25f_doc_chunks[doc_id].get("chunk_id", doc_id)
                if v_chunk_id != b_chunk_id and b_chunk_id not in seen_chunks:
                    b_chunk = bm25f_doc_chunks[doc_id].copy()
                    b_chunk["rrf_score"] = rrf_score * 0.8
                    b_chunk["vector_score"] = 0
                    b_chunk["bm25f_score"] = bm25f_doc_chunks[doc_id].get("score", 0)
                    results.append(b_chunk)
                    seen_chunks.add(b_chunk_id)

            chunk_id = chunk.get("chunk_id", doc_id)
            if chunk_id not in seen_chunks:
                results.append(chunk)
                seen_chunks.add(chunk_id)

        return results[:top_k]

    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档（软删除，标记已删除，检索时跳过）
        注意：向量数据仍在 FAISS 中，节省重建索引开销
        """
        with self._lock:
            if doc_id not in self._doc_meta:
                return False

            self._deleted_docs.add(doc_id)
            self._save_to_disk()

        logger.info(f"文档 {doc_id} 已标记删除")
        return True

    def get_document_chunks(self, doc_id: str) -> List[dict]:
        """获取文档的所有文本块"""
        with self._lock:
            if doc_id not in self._doc_to_indices:
                return []
            indices = self._doc_to_indices[doc_id]
            chunks = []
            for i, idx in enumerate(indices):
                if idx < len(self._chunk_meta):
                    chunk = self._chunk_meta[idx].copy()
                    chunk["index"] = i  # 动态添加索引
                    chunks.append(chunk)
            return chunks

    def get_all_documents(self) -> List[dict]:
        """获取所有文档信息（排除已删除）"""
        with self._lock:
            return [
                {"doc_id": doc_id, "chunk_count": len(indices), **meta}
                for doc_id, indices in self._doc_to_indices.items()
                if doc_id not in self._deleted_docs
                for meta in [self._doc_meta.get(doc_id, {})]
            ]

    def get_stats(self) -> dict:
        """获取存储统计信息"""
        with self._lock:
            total_chunks = sum(len(v) for v in self._doc_to_indices.items() if v[0] not in self._deleted_docs)
            return {
                "total_documents": len(self._doc_meta) - len(self._deleted_docs),
                "total_chunks": self._index.ntotal,
                "store_type": "faiss",
                "index_path": str(self._index_path),
            }

    def clear(self):
        """清空所有数据（危险操作）"""
        with self._lock:
            self._init_index()
            self._chunk_meta.clear()
            self._doc_to_indices.clear()
            self._doc_meta.clear()
            self._deleted_docs.clear()
            if self._index_path.exists():
                self._index_path.unlink()
            if self._meta_path.exists():
                self._meta_path.unlink()
        logger.warning("向量库已清空")


# 全局单例
vector_store = VectorStore()
