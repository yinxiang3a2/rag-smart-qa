"""
对话 API (RAG Q&A)
POST /api/v1/chat  - 执行RAG问答
"""
import logging
from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    SourceDocument,
    BaseResponse,
)
from ..services.rag_service import rag_service, get_conversation_history, get_all_sessions, get_all_sessions_with_titles, delete_session, clear_all_sessions
from ..services.vector_store import vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["智能问答"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    RAG 智能问答端点
    接收用户问题，检索相关文档并生成回答
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        result = rag_service.query(
            question=request.query.strip(),
            top_k=request.top_k,
            filters=request.filters,
            session_id=request.session_id,
        )

        sources = [
            SourceDocument(
                doc_id=s["doc_id"],
                doc_name=s["doc_name"],
                content=s.get("content", ""),
                score=s.get("score", 0.0),
                page=s.get("page"),
            )
            for s in result["sources"]
        ]

        return ChatResponse(
            code=200,
            message="success",
            answer=result["answer"],
            sources=sources,
            session_id=result["session_id"],
            history=get_conversation_history(result["session_id"]),
        )
    except Exception as e:
        logger.error(f"问答处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")


@router.get("/chat/sessions")
async def chat_sessions():
    """获取所有会话列表（带标题）"""
    sessions = get_all_sessions_with_titles()
    return {"code": 200, "sessions": sessions}


@router.get("/chat/history/{session_id}")
async def get_session_history(session_id: str):
    """获取指定会话的历史消息"""
    from app.services.rag_service import get_conversation_history
    history = get_conversation_history(session_id, max_turns=20)
    return {"code": 200, "session_id": session_id, "history": history}


@router.delete("/chat/session/{session_id}")
async def api_delete_session(session_id: str):
    """删除指定会话"""
    success = delete_session(session_id)
    if success:
        return {"code": 200, "message": f"会话 {session_id[:8]} 已删除"}
    return {"code": 404, "message": "会话不存在"}


@router.delete("/chat/sessions")
async def api_clear_all_sessions():
    """清空所有会话"""
    clear_all_sessions()
    return {"code": 200, "message": "所有会话已清空"}


@router.get("/chat/health")
async def chat_health():
    """对话服务健康检查"""
    stats = vector_store.get_stats()
    return {
        "status": "ok",
        "message": "问答服务正常运行",
        "stats": stats,
    }
