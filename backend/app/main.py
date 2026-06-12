"""
FastAPI 应用主入口
"""
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api.upload import router as upload_router
from .api.chat import router as chat_router
from .api.document import router as document_router
from .api.memory import router as memory_router
from .api.skills import router as skills_router
from .utils.file_utils import ensure_directories

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _startup():
    """应用启动时执行"""
    logger.info(f"🚀 {settings.PROJECT_NAME} v{settings.PROJECT_VERSION} 启动中...")
    ensure_directories()
    logger.info(f"📁 上传目录: {settings.UPLOAD_DIR}")
    logger.info(f"📁 向量库目录: {settings.VECTOR_DB_DIR}")
    logger.info(f"📝 所有API密钥使用占位符 'xxx'，后续需替换为真实配置")


def _shutdown():
    """应用关闭时执行"""
    logger.info("👋 服务关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=settings.PROJECT_DESCRIPTION,
)

# 注册生命周期事件
app.add_event_handler("startup", _startup)
app.add_event_handler("shutdown", _shutdown)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(document_router)
app.include_router(memory_router)
app.include_router(skills_router)


@app.get("/")
async def root():
    """根路径 - API 概览"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "description": settings.PROJECT_DESCRIPTION,
        "endpoints": {
            "POST /api/v1/upload": "上传文件(Word/PDF/图片)",
            "POST /api/v1/chat": "RAG智能问答",
            "GET /api/v1/documents": "文档列表",
            "GET /api/v1/documents/{id}": "文档详情",
            "DELETE /api/v1/documents/{id}": "删除文档",
            "GET /docs": "Swagger API文档",
        },
        "note": "所有API密钥当前使用 'xxx' 占位，请替换为真实配置后使用",
    }
