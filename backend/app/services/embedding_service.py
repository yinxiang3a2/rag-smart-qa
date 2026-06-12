"""
嵌入服务
负责将文本转换为向量表示，使用 MiniMax embo-01 模型
"""
import logging
import time
from typing import List
import os

import requests

# 清除 SOCKS 代理，避免 httpx/requests 报错
for _key in ("all_proxy", "ALL_PROXY"):
    os.environ.pop(_key, None)

from ..config import settings

logger = logging.getLogger(__name__)

# MiniMax 嵌入 API 端点（与 LLM 端点不同）
MINIMAX_EMBEDDING_URL = "https://api.minimax.chat/v1/embeddings"


class EmbeddingService:
    """
    嵌入服务
    使用 MiniMax embo-01 将文本转换为向量
    支持 RPM 限流自动重试
    """

    def __init__(self):
        self.api_key = settings.EMBEDDING_API_KEY
        self.model_name = settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.EMBEDDING_DIMENSION
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        logger.info(f"MiniMax 嵌入模型已初始化: {self.model_name}，维度: {self.dimension}")

    def _request(self, texts: List[str], embed_type: str) -> List[List[float]]:
        """发送嵌入请求，支持限流重试（最多3次）"""
        for attempt in range(3):
            try:
                resp = requests.post(
                    MINIMAX_EMBEDDING_URL,
                    headers=self._headers,
                    json={"model": self.model_name, "texts": texts, "type": embed_type},
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("base_resp", {}).get("status_code", 0) != 0:
                    msg = data["base_resp"]["status_msg"]
                    # RPM 限流：等待 1 秒后重试
                    if "rate limit" in msg.lower() or "RPM" in msg:
                        wait = 2 ** attempt  # 1s, 2s, 4s
                        logger.warning(f"触发 RPM 限流，等待 {wait}s 后重试...")
                        time.sleep(wait)
                        continue
                    raise RuntimeError(f"MiniMax 嵌入 API 错误: {msg}")

                return data["vectors"]

            except requests.exceptions.RequestException as e:
                if attempt < 2:
                    logger.warning(f"嵌入请求失败({attempt+1}/3)，重试: {e}")
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise RuntimeError("嵌入请求重试次数耗尽")

    def embed_text(self, text: str) -> List[float]:
        """将单条文本转换为向量（与 db 类型一致，用于检索）"""
        vectors = self._request([text], embed_type="db")
        return vectors[0]

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量将文本转换为向量（索引用 db 类型）"""
        if not texts:
            return []
        logger.info(f"批量嵌入，文本数量: {len(texts)}")
        return self._request(texts, embed_type="db")


# 全局单例
embedding_service = EmbeddingService()