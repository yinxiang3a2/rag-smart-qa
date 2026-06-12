"""
分层记忆管理系统 v2.0
├── 会话语料：corpus/YYYY-MM-DD.txt（按天聚合）
├── 短期记忆索引：index/short-term-recall.json（带热度追踪）
├── 每日日志：daily/YYYY-MM-DD.md（可读格式）
└── 长期记忆：MEMORY.md（用户画像）
"""
import json
import logging
import os
import re
import hashlib
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from ..config import settings

logger = logging.getLogger(__name__)

# BM25F 中文检索
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("jieba 未安装，中文分词降级")

# ========== 路径配置 ==========
MEMORY_DIR = settings.BASE_DIR / "memory"
CORPUS_DIR = MEMORY_DIR / "corpus"
INDEX_DIR = MEMORY_DIR / "index"
DAILY_DIR = MEMORY_DIR / "daily"
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"

# 确保目录存在
CORPUS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
DAILY_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = INDEX_DIR / "short-term-recall.json"

# BM25F 参数
BM25_K1 = 1.5
BM25_B = 0.75
BM25F_FIELD_WEIGHTS = {
    "key": 2.0,      # 索引key权重高
    "tags": 1.5,     # 标签次之
    "content": 1.0,  # 内容权重
}

# RRF 参数
RRF_K = 60  # RRF公式中的常数


# ========== 1. 会话语料管理 (CorpusManager) ==========

def append_to_corpus(date: str, user_msg: str, ai_msg: str) -> dict:
    """
    追加对话到当日语料库
    格式：[HH:MM:SS] USER: xxx\nAI: xxx\n
    """
    corpus_file = CORPUS_DIR / f"{date}.txt"
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    entry = f"[{timestamp}] USER: {user_msg}\nAI: {ai_msg}\n\n"
    
    if corpus_file.exists():
        corpus_file.write_text(corpus_file.read_text(encoding="utf-8") + entry, encoding="utf-8")
    else:
        corpus_file.write_text(entry, encoding="utf-8")
    
    return {"code": 200, "path": str(corpus_file)}


def get_corpus_by_date(date: str) -> dict:
    """获取指定日期的会话语料"""
    corpus_file = CORPUS_DIR / f"{date}.txt"
    if not corpus_file.exists():
        return {"code": 404, "message": "该日期无会话语料"}
    
    content = corpus_file.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    
    return {
        "code": 200,
        "date": date,
        "content": content,
        "line_count": len(lines),
        "entries": _parse_corpus_entries(content)
    }


def get_all_corpus() -> list:
    """获取所有会话语料"""
    corpus_list = []
    for f in sorted(CORPUS_DIR.glob("*.txt"), reverse=True):
        content = f.read_text(encoding="utf-8")
        corpus_list.append({
            "date": f.stem,
            "content": content,
            "size": len(content)
        })
    return corpus_list


def _parse_corpus_entries(content: str) -> list:
    """解析语料内容为条目列表"""
    entries = []
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        if block.startswith("["):
            match = re.match(r"\[(\d{2}:\d{2}:\d{2})\] (USER|AI): (.+)", block.split("\n")[0])
            if match:
                timestamp, role, text = match.groups()
                entries.append({
                    "timestamp": timestamp,
                    "role": role,
                    "text": text.strip(),
                    "raw": block
                })
    return entries


# ========== 2. 短期记忆索引 (ShortTermIndex) ==========

def _load_index() -> dict:
    """加载索引文件"""
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return {"entries": {}, "stats": {"totalEntries": 0, "lastUpdated": None}}


def _save_index(index_data: dict):
    """保存索引文件"""
    INDEX_FILE.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_index_entry(
    corpus_date: str,
    line_start: int,
    line_end: int,
    key: str,
    tags: List[str] = None
) -> str:
    """
    添加索引条目
    返回 entry_key
    """
    entry_key = f"corpus:{corpus_date}.txt:{line_start}:{line_end}"
    
    index_data = _load_index()
    
    index_data["entries"][entry_key] = {
        "key": key,
        "path": f"corpus/{corpus_date}.txt",
        "startLine": line_start,
        "endLine": line_end,
        "recallCount": 0,
        "dailyCount": 0,
        "conceptTags": tags or [],
        "createdAt": datetime.now().isoformat(),
        "lastRecalledAt": None
    }
    
    index_data["stats"]["totalEntries"] = len(index_data["entries"])
    index_data["stats"]["lastUpdated"] = datetime.now().isoformat()
    
    _save_index(index_data)
    return entry_key


def increment_recall(entry_key: str) -> dict:
    """增加召回计数"""
    index_data = _load_index()
    
    if entry_key in index_data["entries"]:
        entry = index_data["entries"][entry_key]
        entry["recallCount"] = entry.get("recallCount", 0) + 1
        entry["dailyCount"] = entry.get("dailyCount", 0) + 1
        entry["lastRecalledAt"] = datetime.now().isoformat()
        _save_index(index_data)
        return {"code": 200, "recallCount": entry["recallCount"]}
    
    return {"code": 404, "message": "索引条目不存在"}


def _simple_tokenize(text: str) -> List[str]:
    """简单的中文分词（降级用）"""
    return _tokenize_chinese(text)


def search_index(query: str, threshold: float = 0.0, use_bm25f: bool = True) -> list:
    """
    搜索索引（BM25F + RRF混合检索）
    
    Args:
        query: 查询文本
        threshold: 得分阈值
        use_bm25f: 是否使用BM25F（否则使用简化关键词匹配）
    """
    index_data = _load_index()
    
    if not index_data["entries"]:
        return []
    
    if use_bm25f and JIEBA_AVAILABLE:
        # 使用BM25F + RRF混合检索
        hybrid_results = hybrid_search(query, top_k=20)
        
        results = []
        for r in hybrid_results:
            if r.get("rrf_score", 0) > 0 or r.get("bm25f_score", 0) > 0:
                # 从原始索引中找到完整信息
                entry_key = r.get("entryKey")
                if entry_key and entry_key in index_data["entries"]:
                    entry = index_data["entries"][entry_key].copy()
                    entry["entryKey"] = entry_key
                    entry["score"] = r.get("rrf_score") or r.get("bm25f_score", 0)
                    if "vector_score" in r:
                        entry["vector_score"] = r["vector_score"]
                    results.append(entry)
        
        # 按score和recallCount排序
        results.sort(key=lambda x: (x.get("score", 0), x.get("recallCount", 0)), reverse=True)
        return results[:20]
    
    # 降级：简化关键词匹配
    results = []
    query_lower = query.lower()
    query_keywords = _simple_tokenize(query)
    
    for key, entry in index_data["entries"].items():
        score = 0.0
        key_lower = entry["key"].lower()
        tags = entry.get("conceptTags", [])
        
        # 1. 精确匹配key
        if query_lower in key_lower:
            score = 2.0
        # 2. 标签匹配
        elif any(query_lower in tag.lower() for tag in tags):
            score = 1.5
        # 3. 关键词匹配
        elif query_keywords:
            match_count = sum(1 for kw in query_keywords 
                           if kw in key_lower or any(kw in tag.lower() for tag in tags))
            if match_count > 0:
                score = match_count / len(query_keywords)
        
        if score > threshold:
            result = entry.copy()
            result["entryKey"] = key
            result["score"] = score
            results.append(result)
    
    results.sort(key=lambda x: (x.get("score", 0), x.get("recallCount", 0)), reverse=True)
    return results[:20]


def get_hot_entries(limit: int = 10) -> list:
    """获取热门条目"""
    index_data = _load_index()
    entries = list(index_data["entries"].values())
    entries.sort(key=lambda x: x.get("recallCount", 0), reverse=True)
    return entries[:limit]


def get_index_stats() -> dict:
    """获取索引统计"""
    index_data = _load_index()
    tags_count = {}
    for entry in index_data["entries"].values():
        for tag in entry.get("conceptTags", []):
            tags_count[tag] = tags_count.get(tag, 0) + 1
    
    return {
        "code": 200,
        "totalEntries": index_data["stats"]["totalEntries"],
        "lastUpdated": index_data["stats"].get("lastUpdated"),
        "topTags": sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:20]
    }


# ========== 3. 每日日志 (DailyLog) ==========

def write_daily_log(date: str, content: str) -> dict:
    """写入每日日志"""
    daily_file = DAILY_DIR / f"{date}.md"
    
    entry = f"\n## [{datetime.now().strftime('%H:%M:%S')}]\n\n{content}\n"
    
    if daily_file.exists():
        daily_file.write_text(daily_file.read_text(encoding="utf-8") + entry, encoding="utf-8")
    else:
        header = f"# 每日日志 {date}\n"
        daily_file.write_text(header + entry, encoding="utf-8")
    
    return {"code": 200, "path": str(daily_file)}


def read_daily_log(date: str = None) -> dict:
    """读取每日日志"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    daily_file = DAILY_DIR / f"{date}.md"
    
    if not daily_file.exists():
        return {"code": 404, "message": "日志不存在"}
    
    return {
        "code": 200,
        "content": daily_file.read_text(encoding="utf-8"),
        "date": date
    }


def list_daily_logs() -> dict:
    """列出所有每日日志"""
    logs = [f.stem for f in sorted(DAILY_DIR.glob("*.md"), reverse=True)]
    return {"code": 200, "logs": logs}


def delete_daily_log(date: str) -> dict:
    """删除指定日期日志"""
    daily_file = DAILY_DIR / f"{date}.md"
    if daily_file.exists():
        daily_file.unlink()
        return {"code": 200, "message": "日志已删除"}
    return {"code": 404, "message": "日志不存在"}


# ========== 4. 长期记忆 (LongTermMemory) ==========

def read_long_term_memory() -> dict:
    """读取长期记忆"""
    if not MEMORY_FILE.exists():
        return {"code": 200, "content": "# 用户画像\n\n", "path": str(MEMORY_FILE)}
    
    return {
        "code": 200,
        "content": MEMORY_FILE.read_text(encoding="utf-8"),
        "path": str(MEMORY_FILE)
    }


def write_long_term_memory(content: str) -> dict:
    """写入长期记忆（覆盖）"""
    MEMORY_FILE.write_text(content, encoding="utf-8")
    return {"code": 200, "message": "长期记忆已更新", "path": str(MEMORY_FILE)}


def append_long_term_memory(content: str) -> dict:
    """追加到长期记忆"""
    if MEMORY_FILE.exists():
        existing = MEMORY_FILE.read_text(encoding="utf-8")
        MEMORY_FILE.write_text(existing + "\n" + content, encoding="utf-8")
    else:
        MEMORY_FILE.write_text(content, encoding="utf-8")
    return {"code": 200, "message": "已追加到长期记忆"}


def delete_long_term_memory() -> dict:
    """删除长期记忆"""
    if MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
    return {"code": 200, "message": "长期记忆已清空"}


# ========== 5. 记忆检索 (MemorySearch) ==========

def search_corpus(query: str, threshold: float = 0.0) -> list:
    """
    搜索会话语料（关键词匹配）
    """
    results = []
    query_lower = query.lower()
    query_keywords = _simple_tokenize(query)
    seen_dates = set()
    
    for f in sorted(CORPUS_DIR.glob("*.txt"), reverse=True):
        content = f.read_text(encoding="utf-8")
        content_lower = content.lower()
        
        # 检查是否匹配
        score = 0.0
        if query_lower in content_lower:
            score = 2.0  # 精确匹配
        elif query_keywords and any(kw in content_lower for kw in query_keywords):
            score = 1.0  # 关键词匹配
        
        if score > threshold and f.stem not in seen_dates:
            seen_dates.add(f.stem)
            # 找到匹配位置，提取上下文
            idx = content_lower.find(query_lower if score == 2.0 else query_keywords[0])
            start = max(0, idx - 100) if idx >= 0 else 0
            # 提取用户消息
            user_msgs = re.findall(r'USER: (.+)', content)
            snippet = user_msgs[0][:200] if user_msgs else content[start:start+200]
            results.append({
                "date": f.stem,
                "snippet": snippet,
                "score": score
            })
    
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:5]


def memory_search(query: str, corpus: str = "all") -> dict:
    """
    记忆全局搜索（BM25算法）
    corpus: all | corpus | index | daily | longterm
    """
    results = {
        "corpus": [],
        "index": [],
        "daily": [],
        "longterm": [],
        "query": query
    }
    
    # 搜索会话语料（BM25）
    if corpus in ("all", "corpus"):
        results["corpus"] = search_corpus(query)
    
    # 搜索索引（BM25）
    if corpus in ("all", "index"):
        index_results = search_index(query)
        results["index"] = index_results
    
    # 搜索每日日志（关键词匹配 + 扩展上下文）
    if corpus in ("all", "daily"):
        query_lower = query.lower()
        for f in DAILY_DIR.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            if query_lower in content.lower():
                idx = content.lower().find(query_lower)
                start = max(0, idx - 100)
                end = min(len(content), idx + len(query) + 200)
                results["daily"].append({
                    "date": f.stem,
                    "snippet": content[start:end]
                })
    
    # 搜索长期记忆
    if corpus in ("all", "longterm") and MEMORY_FILE.exists():
        content = MEMORY_FILE.read_text(encoding="utf-8")
        if query_lower in content.lower():
            idx = content.lower().find(query_lower)
            start = max(0, idx - 50)
            end = min(len(content), idx + len(query) + 100)
            results["longterm"].append({
                "snippet": content[start:end]
            })
    
    return {"code": 200, "results": results}


# ========== 6. 记忆系统统计 ==========

def get_memory_stats() -> dict:
    """获取记忆系统统计"""
    corpus_count = len(list(CORPUS_DIR.glob("*.txt")))
    daily_count = len(list(DAILY_DIR.glob("*.md")))
    index_data = _load_index()
    
    return {
        "code": 200,
        "corpus_count": corpus_count,
        "daily_logs_count": daily_count,
        "index_entries": index_data["stats"]["totalEntries"],
        "long_term_exists": MEMORY_FILE.exists(),
        "last_index_update": index_data["stats"].get("lastUpdated"),
        "dirs": {
            "corpus": str(CORPUS_DIR),
            "index": str(INDEX_DIR),
            "daily": str(DAILY_DIR),
            "longterm": str(MEMORY_DIR)
        }
    }


# ========== 7. 清理功能 ==========

def clear_all_memory() -> dict:
    """清空所有记忆"""
    for f in CORPUS_DIR.glob("*.txt"):
        f.unlink()
    for f in DAILY_DIR.glob("*.md"):
        f.unlink()
    if INDEX_FILE.exists():
        INDEX_FILE.unlink()
    if MEMORY_FILE.exists():
        MEMORY_FILE.unlink()
    return {"code": 200, "message": "所有记忆已清空"}


def clear_corpus() -> dict:
    """清空会话语料"""
    for f in CORPUS_DIR.glob("*.txt"):
        f.unlink()
    return {"code": 200, "message": "会话语料已清空"}


# ========== 8. BM25F + RRF 混合检索 ==========

def _tokenize_chinese(text: str) -> List[str]:
    """中文分词"""
    if JIEBA_AVAILABLE:
        return list(jieba.cut(text))
    # 降级：按非中文字符分割
    return [t for t in re.split(r'[^\u4e00-\u9fff\w]+', text) if t]


def _build_index_for_bm25f() -> Tuple[List[Dict], List[Dict[str, List[str]]]]:
    """
    构建BM25F索引
    Returns: (docs, tokenized_docs)
    """
    index_data = _load_index()
    docs = []
    tokenized_docs = []
    
    for key, entry in index_data["entries"].items():
        # 构建多字段文档
        doc = {
            "entryKey": key,
            **entry
        }
        
        # 提取各字段文本
        key_text = entry.get("key", "")
        tags_text = " ".join(entry.get("conceptTags", []))
        path_text = entry.get("path", "")
        
        # 分词
        key_tokens = _tokenize_chinese(key_text)
        tags_tokens = _tokenize_chinese(tags_text)
        path_tokens = _tokenize_chinese(path_text)
        
        docs.append(doc)
        tokenized_docs.append({
            "key": key_tokens,
            "tags": tags_tokens,
            "content": key_tokens + tags_tokens  # content = key + tags
        })
    
    return docs, tokenized_docs


def _bm25f_score(query_tokens: List[str], doc_tokens: Dict[str, List[str]], 
                field_weights: Dict[str, float], avg_field_len: Dict[str, float],
                doc_field_lens: Dict[str, float]) -> float:
    """
    BM25F算法实现
    
    BM25F公式：
    score = Σ IDF(t) × (tf(t,d)×(k1+1)) / (tf(t,d) + k1×(1-b+b×|d|/avgdl))
    
    多字段扩展：
    tf(t,d) = Σ wt×tf(t,field)  (字段加权词频)
    |d| = Σ wt×len(field)       (字段加权文档长度)
    """
    score = 0.0
    N = len(docs) if 'docs' in dir() else 1  # 简化
    
    for term in query_tokens:
        # IDF计算 (简化版)
        df = 1  # 假设每个词至少出现在1个文档
        idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
        
        # 字段加权词频
        weighted_tf = 0.0
        weighted_len = 0.0
        
        for field, tokens in doc_tokens.items():
            wt = field_weights.get(field, 1.0)
            tf = tokens.count(term)
            weighted_tf += wt * tf
            weighted_len += wt * len(tokens)
        
        if weighted_tf == 0:
            continue
        
        # 文档长度归一化
        avg_len = sum(avg_field_len.values()) / len(avg_field_len) if avg_field_len else 1
        doc_len_norm = weighted_len / avg_len if avg_len > 0 else 1
        
        # BM25F公式
        numerator = weighted_tf * (BM25_K1 + 1)
        denominator = weighted_tf + BM25_K1 * (1 - BM25_B + BM25_B * doc_len_norm)
        
        score += idf * numerator / denominator if denominator > 0 else 0
    
    return score


def _compute_bm25f_scores(query: str) -> List[Tuple[int, float]]:
    """
    对查询计算所有文档的BM25F得分
    Returns: [(doc_idx, score), ...]
    """
    docs, tokenized_docs = _build_index_for_bm25f()
    if not docs:
        return []
    
    query_tokens = _tokenize_chinese(query)
    if not query_tokens:
        return []
    
    # 计算平均字段长度
    avg_field_lens = {"key": 0, "tags": 0, "content": 0}
    for doc_tokens in tokenized_docs:
        for field in avg_field_lens:
            avg_field_lens[field] += len(doc_tokens.get(field, []))
    for field in avg_field_lens:
        avg_field_lens[field] /= len(tokenized_docs) if tokenized_docs else 1
    
    # 计算每个文档的得分
    scores = []
    for i, doc_tokens in enumerate(tokenized_docs):
        score = _bm25f_score(
            query_tokens, doc_tokens, 
            BM25F_FIELD_WEIGHTS, avg_field_lens, {}
        )
        if score > 0:
            scores.append((i, score))
    
    # 按得分降序
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _rrf_fusion(ranked_lists: List[List[Tuple[str, float]]], k: int = 60) -> List[Tuple[str, float]]:
    """
    RRF (Reciprocal Rank Fusion) 融合多个排序结果
    
    RRF公式：
    RRF_score(d) = Σ 1/(k + rank(d))
    
    Args:
        ranked_lists: 多个排序列表，每个元素是 [(doc_id, score), ...]
        k: RRF常数（通常60）
    
    Returns:
        融合后的排序列表
    """
    rrf_scores = {}
    
    for ranked_list in ranked_lists:
        for rank, (doc_id, score) in enumerate(ranked_list, 1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            # 使用排名而不是原始分数
            rrf_scores[doc_id] += 1.0 / (k + rank)
    
    # 按RRF得分排序
    fused = [(doc_id, score) for doc_id, score in rrf_scores.items()]
    fused.sort(key=lambda x: x[1], reverse=True)
    return fused


def hybrid_search(query: str, top_k: int = 5) -> List[Dict]:
    """
    BM25F + 语义向量 + RRF 混合检索
    
    融合策略：
    1. BM25F检索（关键词匹配）
    2. 向量检索（语义相似度）- 通过embedding
    3. RRF融合两个排序结果
    """
    results = []
    ranked_lists = []
    
    # 1. BM25F检索
    bm25f_scores = _compute_bm25f_scores(query)
    docs, _ = _build_index_for_bm25f()
    
    bm25f_ranked = []
    for idx, score in bm25f_scores:
        doc = docs[idx]
        doc_id = doc["entryKey"]
        bm25f_ranked.append((doc_id, score))
        # 记录doc_id到idx的映射
        if not any(d["entryKey"] == doc_id for d in results):
            results.append({**doc, "bm25f_score": score})
    ranked_lists.append(bm25f_ranked)
    
    # 2. 向量检索（如果可用）
    try:
        from .vector_store import vector_store
        vector_results = vector_store.search(query, top_k=top_k)
        
        vector_ranked = []
        for i, chunk in enumerate(vector_results):
            doc_id = chunk["doc_id"]
            vector_ranked.append((doc_id, chunk["score"]))
            # 合并到results
            if not any(d.get("doc_id") == doc_id for d in results):
                results.append({
                    "entryKey": doc_id,
                    "key": chunk.get("content", "")[:100],
                    "vector_score": chunk["score"],
                    "doc_id": doc_id
                })
        ranked_lists.append(vector_ranked)
    except Exception as e:
        logger.warning(f"向量检索失败: {e}")
    
    # 3. RRF融合
    if len(ranked_lists) >= 2:
        fused = _rrf_fusion(ranked_lists, k=RRF_K)
        
        # 更新results中的融合得分
        fused_scores = {doc_id: score for doc_id, score in fused}
        for r in results:
            key = r.get("entryKey") or r.get("doc_id")
            if key in fused_scores:
                r["rrf_score"] = fused_scores[key]
        
        # 按RRF得分排序
        results.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)
    else:
        # 只有BM25F结果，按BM25F排序
        results.sort(key=lambda x: x.get("bm25f_score", 0), reverse=True)
    
    return results[:top_k]


def clear_index() -> dict:
    """清空索引"""
    if INDEX_FILE.exists():
        INDEX_FILE.unlink()
    return {"code": 200, "message": "索引已清空"}
