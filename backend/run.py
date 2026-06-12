"""
后端启动脚本
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,  # 开发环境关闭热重载，避免内存数据丢失
        log_level="info",
    )
