"""
Pydantic 数据模型定义
所有API请求/响应的数据结构
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ========== 枚举类型 ==========

class DocumentType(str, Enum):
    """文档类型枚举"""
    PDF = "pdf"
    WORD = "word"
    IMAGE = "image"
    TEXT = "text"
    MARKDOWN = "markdown"


class DocumentStatus(str, Enum):
    """文档处理状态"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


# ========== 通用响应模型 ==========

class BaseResponse(BaseModel):
    """基础响应模型"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[dict] = Field(default=None, description="响应数据")


class PaginatedResponse(BaseModel):
    """分页响应模型"""
    code: int = Field(default=200)
    message: str = Field(default="success")
    data: List[dict] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    page_size: int = Field(default=10)


# ========== 文档模型 ==========

class DocumentInfo(BaseModel):
    """文档信息模型"""
    id: str = Field(description="文档ID")
    filename: str = Field(description="原始文件名")
    file_type: DocumentType = Field(description="文档类型")
    file_size: int = Field(description="文件大小(字节)")
    status: DocumentStatus = Field(default=DocumentStatus.UPLOADED, description="处理状态")
    chunk_count: int = Field(default=0, description="文本块数量")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    metadata: dict = Field(default_factory=dict, description="元数据")


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""
    code: int = Field(default=200)
    message: str = Field(default="文件上传成功，正在处理中...")
    document: DocumentInfo


# ========== 对话模型 ==========

class ChatRequest(BaseModel):
    """对话请求模型"""
    query: str = Field(description="用户问题")
    session_id: Optional[str] = Field(default=None, description="会话ID，用于多轮对话")
    top_k: Optional[int] = Field(default=5, description="检索文档数量")
    filters: Optional[dict] = Field(default=None, description="文档过滤条件")


class SourceDocument(BaseModel):
    """引用来源文档"""
    doc_id: str = Field(description="来源文档ID")
    doc_name: str = Field(description="来源文档名称")
    content: str = Field(description="引用内容片段")
    score: float = Field(description="相关性分数")
    page: Optional[int] = Field(default=None, description="页码(如有)")


class ChatResponse(BaseModel):
    """对话响应模型"""
    code: int = Field(default=200)
    message: str = Field(default="success")
    answer: str = Field(description="模型回答")
    sources: List[SourceDocument] = Field(default_factory=list, description="引用来源")
    session_id: str = Field(description="会话ID")
    history: List[dict] = Field(default_factory=list, description="对话历史")


# ========== 文档删除请求 ==========

class DocumentDeleteRequest(BaseModel):
    """文档删除请求"""
    doc_ids: List[str] = Field(description="要删除的文档ID列表")
