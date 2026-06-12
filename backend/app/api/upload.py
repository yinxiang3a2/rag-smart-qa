"""
文件上传 API
POST /api/v1/upload  - 上传文件(Word/PDF/图片)
"""
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from ..models.schemas import (
    BaseResponse,
    DocumentUploadResponse,
    DocumentInfo,
    DocumentType,
    DocumentStatus,
)
from ..services.document_processor import document_processor
from ..services.vector_store import vector_store
from ..utils.file_utils import (
    validate_file_type,
    validate_file_size,
    save_uploaded_file,
    get_file_extension,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["文件上传"])


def _get_document_type(ext: str, category: str) -> DocumentType:
    """根据扩展名和分类获取文档类型"""
    if category == "image":
        return DocumentType.IMAGE

    ext_map = {
        ".pdf": DocumentType.PDF,
        ".docx": DocumentType.WORD,
        ".doc": DocumentType.WORD,
        ".txt": DocumentType.TEXT,
        ".md": DocumentType.MARKDOWN,
    }
    return ext_map.get(ext, DocumentType.TEXT)


def _process_document_background(doc_id: str, file_path: Path, file_type: str, filename: str, ext: str):
    """
    后台处理文档：提取文本 -> 分块 -> 向量化 -> 存入向量库
    """
    try:
        # 1. 提取文本
        text = document_processor.extract_text(file_path, file_type)

        # 2. 文本分块
        chunks = document_processor.chunk_text(text)

        # 3. 存入向量库
        metadata = {
            "filename": filename,
            "file_type": file_type,
            "ext": ext,
            "file_path": str(file_path),
            "created_at": datetime.now().isoformat(),
        }
        chunk_count = vector_store.add_document(doc_id, chunks, metadata)

        logger.info(f"文档 {doc_id} ({filename}) 处理完成，共 {chunk_count} 个文本块")
    except Exception as e:
        logger.error(f"文档 {doc_id} ({filename}) 处理失败: {e}")


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_file(
    file: UploadFile = File(..., description="上传文件(Word/PDF/图片)"),
    background_tasks: BackgroundTasks = None,
):
    """
    上传文件端点
    支持格式: PDF, Word(.docx/.doc), TXT, MD, JPG, PNG 等
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    # 1. 读取文件内容
    file_content = await file.read()
    file_size = len(file_content)

    # 2. 验证文件类型
    is_valid, file_category = validate_file_type(file.filename)
    if not is_valid:
        allowed = ".pdf, .docx, .doc, .txt, .md, .jpg, .png"
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。支持: {allowed}"
        )

    # 3. 验证文件大小
    if not validate_file_size(file_size):
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 50MB"
        )

    # 4. 保存文件
    doc_id, saved_filename, file_path = save_uploaded_file(file_content, file.filename)
    ext = get_file_extension(file.filename)

    # 5. 构建文档信息
    doc_type = _get_document_type(ext, file_category)
    doc_info = DocumentInfo(
        id=doc_id,
        filename=file.filename,
        file_type=doc_type,
        file_size=file_size,
        status=DocumentStatus.PROCESSING,
        metadata={"ext": ext, "category": file_category},
    )

    # 6. 后台处理文档
    background_tasks.add_task(
        _process_document_background,
        doc_id, file_path, file_category, file.filename, ext
    )

    return DocumentUploadResponse(
        code=200,
        message=f"文件 {file.filename} 上传成功，正在后台处理...",
        document=doc_info,
    )


@router.get("/upload/health")
async def upload_health():
    """上传服务健康检查"""
    return {"status": "ok", "message": "上传服务正常运行"}
