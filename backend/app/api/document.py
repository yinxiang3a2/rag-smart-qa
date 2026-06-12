"""
文档管理 API
GET  /api/v1/documents       - 获取文档列表
GET  /api/v1/documents/{id}  - 获取文档详情
DELETE /api/v1/documents/{id} - 删除文档
"""
import logging
from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    BaseResponse,
    PaginatedResponse,
    DocumentDeleteRequest,
)
from ..services.vector_store import vector_store
from ..utils.file_utils import delete_uploaded_file
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["文档管理"])


@router.get("/documents", response_model=PaginatedResponse)
async def list_documents(page: int = 1, page_size: int = 10):
    """
    获取文档列表
    """
    all_docs = vector_store.get_all_documents()

    # 简单分页
    total = len(all_docs)
    start = (page - 1) * page_size
    end = start + page_size
    paged_docs = all_docs[start:end]

    return PaginatedResponse(
        code=200,
        message="success",
        data=paged_docs,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{doc_id}", response_model=BaseResponse)
async def get_document(doc_id: str):
    """
    获取文档详情（包含所有文本块）
    """
    chunks = vector_store.get_document_chunks(doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")

    # 不返回向量数据，只返回文本信息
    chunk_contents = [
        {
            "chunk_id": c["chunk_id"],
            "index": c["index"],
            "content": c["content"],
            "created_at": c["created_at"],
        }
        for c in chunks
    ]

    return BaseResponse(
        code=200,
        message="success",
        data={
            "doc_id": doc_id,
            "chunks": chunk_contents,
            "total_chunks": len(chunks),
        }
    )


@router.delete("/documents/{doc_id}", response_model=BaseResponse)
async def delete_document(doc_id: str):
    """
    删除指定文档
    """
    # 从向量存储中删除
    removed = vector_store.delete_document(doc_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")

    # 尝试删除本地文件
    for ext in settings.ALLOWED_DOC_EXTENSIONS | settings.ALLOWED_IMAGE_EXTENSIONS:
        file_path = settings.UPLOAD_DIR / f"{doc_id}{ext}"
        if file_path.exists():
            delete_uploaded_file(file_path)

    return BaseResponse(
        code=200,
        message=f"文档 {doc_id} 已删除",
    )


@router.delete("/documents", response_model=BaseResponse)
async def batch_delete_documents(request: DocumentDeleteRequest):
    """
    批量删除文档
    """
    deleted = []
    failed = []

    for doc_id in request.doc_ids:
        removed = vector_store.delete_document(doc_id)
        if removed:
            # 删除本地文件
            for ext in settings.ALLOWED_DOC_EXTENSIONS | settings.ALLOWED_IMAGE_EXTENSIONS:
                file_path = settings.UPLOAD_DIR / f"{doc_id}{ext}"
                if file_path.exists():
                    delete_uploaded_file(file_path)
            deleted.append(doc_id)
        else:
            failed.append(doc_id)

    return BaseResponse(
        code=200,
        message=f"成功删除 {len(deleted)} 个文档",
        data={"deleted": deleted, "failed": failed},
    )
