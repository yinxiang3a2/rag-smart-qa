"""
文件工具模块
提供文件保存、验证、类型判断等通用功能
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from ..config import settings


def generate_doc_id() -> str:
    """生成唯一文档ID"""
    return uuid.uuid4().hex[:16]


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写）"""
    return Path(filename).suffix.lower()


def validate_file_type(filename: str) -> Tuple[bool, str]:
    """
    验证文件类型是否允许上传
    返回: (是否允许, 文件类型分类)
    """
    ext = get_file_extension(filename)

    if ext in settings.ALLOWED_DOC_EXTENSIONS:
        return True, "document"

    if ext in settings.ALLOWED_IMAGE_EXTENSIONS:
        return True, "image"

    return False, ""


def validate_file_size(file_size: int) -> bool:
    """验证文件大小是否在限制内"""
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    return file_size <= max_bytes


def save_uploaded_file(file_content: bytes, filename: str) -> Tuple[str, str, Path]:
    """
    保存上传的文件到本地
    返回: (doc_id, 保存后的文件名, 文件保存路径)
    """
    doc_id = generate_doc_id()
    ext = get_file_extension(filename)
    saved_filename = f"{doc_id}{ext}"
    save_path = settings.UPLOAD_DIR / saved_filename

    with open(save_path, "wb") as f:
        f.write(file_content)

    return doc_id, saved_filename, save_path


def get_file_size_mb(file_path: Path) -> float:
    """获取文件大小（MB）"""
    return file_path.stat().st_size / (1024 * 1024)


def delete_uploaded_file(file_path: Path) -> bool:
    """删除上传的文件"""
    try:
        if file_path.exists():
            os.remove(file_path)
        return True
    except Exception:
        return False


def ensure_directories():
    """确保必要的目录存在"""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.VECTOR_DB_DIR, exist_ok=True)
