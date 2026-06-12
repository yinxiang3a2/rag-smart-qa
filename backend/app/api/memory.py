"""
记忆管理API v2.0
提供分层记忆的读写和检索接口
├── 会话语料：corpus/YYYY-MM-DD.txt
├── 短期记忆索引：index/short-term-recall.json
├── 每日日志：daily/YYYY-MM-DD.md
└── 长期记忆：MEMORY.md
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from app.services.memory_service import (
    # 会话语料
    get_corpus_by_date,
    get_all_corpus,
    # 索引
    search_index,
    get_hot_entries,
    get_index_stats,
    increment_recall,
    # 每日日志
    write_daily_log,
    read_daily_log,
    list_daily_logs,
    delete_daily_log,
    # 长期记忆
    read_long_term_memory,
    write_long_term_memory,
    append_long_term_memory,
    delete_long_term_memory,
    # 记忆检索
    memory_search,
    # 统计
    get_memory_stats,
    # 清理
    clear_all_memory,
    clear_corpus,
    clear_index,
)
from app.services.rag_service import rag_service

router = APIRouter(prefix="/api/v1/memory", tags=["记忆管理"])


# ========== 请求模型 ==========

class DailyLogRequest(BaseModel):
    content: str
    date: Optional[str] = None


class LongTermMemoryRequest(BaseModel):
    content: str


class MemorySearchRequest(BaseModel):
    query: str
    corpus: str = "all"


class RecallRequest(BaseModel):
    entry_key: str


# ========== 会话语料 API ==========

@router.get("/corpus/{date}")
async def api_get_corpus(date: str):
    """获取指定日期的会话语料"""
    return get_corpus_by_date(date)


@router.get("/corpus")
async def api_get_all_corpus():
    """获取所有会话语料列表"""
    corpus_list = get_all_corpus()
    return {"code": 200, "corpus": corpus_list}


# ========== 索引 API ==========

@router.get("/index/search")
async def api_search_index(query: str):
    """搜索短期记忆索引"""
    results = search_index(query)
    return {"code": 200, "results": results}


@router.get("/index/hot")
async def api_get_hot_entries(limit: int = 10):
    """获取热门索引条目"""
    entries = get_hot_entries(limit)
    return {"code": 200, "entries": entries}


@router.get("/index/stats")
async def api_get_index_stats():
    """获取索引统计"""
    return get_index_stats()


@router.post("/index/recall")
async def api_increment_recall(req: RecallRequest):
    """增加召回计数"""
    return increment_recall(req.entry_key)


# ========== 每日日志 API ==========

@router.post("/daily-log")
async def api_write_daily_log(req: DailyLogRequest):
    """写入每日日志"""
    return write_daily_log(req.date or "", req.content)


@router.get("/daily-log/{date}")
async def api_read_daily_log(date: str):
    """读取指定日期日志"""
    return read_daily_log(date)


@router.get("/daily-logs")
async def api_list_daily_logs():
    """列出所有每日日志"""
    return list_daily_logs()


@router.delete("/daily-log/{date}")
async def api_delete_daily_log(date: str):
    """删除指定日期日志"""
    return delete_daily_log(date)


# ========== 长期记忆 API ==========

@router.get("/long-term")
async def api_read_long_term():
    """读取长期记忆"""
    return read_long_term_memory()


@router.post("/long-term")
async def api_write_long_term(req: LongTermMemoryRequest):
    """写入长期记忆"""
    return write_long_term_memory(req.content)


@router.post("/long-term/append")
async def api_append_long_term(req: LongTermMemoryRequest):
    """追加到长期记忆"""
    return append_long_term_memory(req.content)


@router.post("/long-term/extract")
async def api_extract_long_term():
    """
    手动触发从索引和语料提取到长期记忆
    从热门索引条目和会话语料中整合提取，生成用户画像
    """
    return rag_service.extract_to_long_term_memory()


@router.delete("/long-term")
async def api_delete_long_term():
    """清空长期记忆"""
    return delete_long_term_memory()


# ========== 记忆检索 API ==========

@router.post("/search")
async def api_memory_search(req: MemorySearchRequest):
    """记忆全局搜索"""
    return memory_search(req.query, req.corpus)


@router.get("/search")
async def api_memory_search_get(query: str, corpus: str = "all"):
    """记忆全局搜索（GET方式）"""
    return memory_search(query, corpus)


# ========== 记忆统计 API ==========

@router.get("/stats")
async def api_memory_stats():
    """获取记忆系统统计"""
    return get_memory_stats()


# ========== 清理 API ==========

@router.delete("/corpus")
async def api_clear_corpus():
    """清空会话语料"""
    return clear_corpus()


@router.delete("/index")
async def api_clear_index():
    """清空索引"""
    return clear_index()


@router.delete("/daily-logs")
async def api_clear_daily_logs():
    """清空所有每日日志"""
    for date in list_daily_logs().get("logs", []):
        delete_daily_log(date)
    return {"code": 200, "message": "所有每日日志已清空"}


@router.delete("/all")
async def api_clear_all_memory():
    """清空所有记忆"""
    return clear_all_memory()
