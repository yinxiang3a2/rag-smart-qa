"""
应用配置模块
集中管理所有配置项，方便后续扩展和修改
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（backend/.env）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 仅清除 SOCKS 代理，保留 HTTP 代理
for _key in ("all_proxy", "ALL_PROXY"):
    os.environ.pop(_key, None)


class Settings:
    """全局配置类"""

    # ---------- 基础配置 ----------
    PROJECT_NAME: str = "RAG智能问答系统"
    PROJECT_VERSION: str = "0.1.0"
    PROJECT_DESCRIPTION: str = "支持Word/PDF/图片上传的RAG检索智能问答系统"

    # ---------- 路径配置 ----------
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    VECTOR_DB_DIR: Path = BASE_DIR / "vector_db"

    # ---------- 文件上传配置 ----------
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_DOC_EXTENSIONS: set = {".pdf", ".docx", ".doc", ".txt", ".md"}
    ALLOWED_IMAGE_EXTENSIONS: set = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}

    # ---------- 文档处理配置 ----------
    CHUNK_SIZE: int = 500           # 文本分块大小（字符数）
    CHUNK_OVERLAP: int = 50         # 分块重叠大小

    # ---------- 向量/嵌入配置 ----------
    EMBEDDING_API_URL: str = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    EMBEDDING_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    EMBEDDING_MODEL_NAME: str = "embo-01"                     # MiniMax 嵌入模型
    EMBEDDING_DIMENSION: int = 1536                           # embo-01 维度
    VECTOR_STORE_TYPE: str = "faiss"                       # 向量数据库类型: chromadb / faiss / milvus

    # ---------- LLM 配置 ----------
    LLM_API_URL: str = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    LLM_API_KEY: str = os.getenv("MINIMAX_API_KEY", "")
    LLM_MODEL_NAME: str = "MiniMax-M2.5"              # MiniMax 大模型
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048

    # ---------- RAG 配置 ----------
    RAG_TOP_K: int = 5                          # 检索返回的Top-K文档块
    RAG_SIMILARITY_THRESHOLD: float = 0.3       # 相似度阈值（余弦相似度，≥30%才引用）

    # ---------- 记忆配置 ----------
    AUTO_MEMORY_ENABLED: bool = True            # 是否开启自动记忆提炼
    AUTO_MEMORY_INTERVAL: int = 10              # 每N条消息触发LLM提炼（默认10条=5轮）

    # ---------- 服务配置 ----------
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list = ["*"]                  # 允许跨域来源，生产环境需限制


settings = Settings()
