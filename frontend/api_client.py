"""
前端 API 客户端 v2.0
封装与后端 FastAPI 的通信
"""
import requests
from typing import Optional, List, Dict, Any
import streamlit as st


class APIClient:
    """
    后端 API 客户端
    所有 API 调用通过此类统一管理，方便后续扩展和替换
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.timeout = 60  # 请求超时时间（秒）

    def _post(self, endpoint: str, data: dict = None, files: dict = None) -> dict:
        """通用 POST 请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            if files:
                response = requests.post(url, files=files, timeout=self.timeout)
            else:
                response = requests.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"code": 503, "message": "无法连接到后端服务，请确保后端已启动"}
        except requests.exceptions.Timeout:
            return {"code": 504, "message": "请求超时，请稍后重试"}
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_data = e.response.json()
                detail = error_data.get("detail", str(e))
            except:
                detail = str(e)
            return {"code": status_code, "message": detail}
        except Exception as e:
            return {"code": 500, "message": f"请求失败: {str(e)}"}

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """通用 GET 请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_data = e.response.json()
                detail = error_data.get("detail", str(e))
            except:
                detail = str(e)
            return {"code": status_code, "message": detail}
        except requests.exceptions.ConnectionError:
            return {"code": 503, "message": "无法连接到后端服务，请确保后端已启动"}
        except Exception as e:
            return {"code": 500, "message": f"请求失败: {str(e)}"}

    def _delete(self, endpoint: str) -> dict:
        """通用 DELETE 请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.delete(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            return {"code": 503, "message": "无法连接到后端服务，请确保后端已启动"}
        except Exception as e:
            return {"code": 500, "message": f"请求失败: {str(e)}"}

    # ========== 文件上传 ==========

    def upload_file(self, file_bytes: bytes, filename: str) -> dict:
        """上传文件"""
        files = {"file": (filename, file_bytes)}
        return self._post("/api/v1/upload", files=files)

    # ========== 智能问答 ==========

    def chat(
        self,
        query: str,
        session_id: Optional[str] = None,
        top_k: int = 5,
    ) -> dict:
        """发送问答请求"""
        data = {
            "query": query,
            "session_id": session_id,
            "top_k": top_k,
        }
        return self._post("/api/v1/chat", data=data)

    # ========== 文档管理 ==========

    def list_documents(self, page: int = 1, page_size: int = 100) -> dict:
        """获取文档列表"""
        return self._get("/api/v1/documents", params={"page": page, "page_size": page_size})

    def get_document(self, doc_id: str) -> dict:
        """获取文档详情"""
        return self._get(f"/api/v1/documents/{doc_id}")

    def delete_document(self, doc_id: str) -> dict:
        """删除文档"""
        return self._delete(f"/api/v1/documents/{doc_id}")

    # ========== 健康检查 ==========

    def health_check(self) -> dict:
        """检查后端服务是否可用"""
        return self._get("/api/v1/chat/health")

    # ========== 会话管理 ==========

    def list_sessions(self) -> dict:
        """获取所有会话列表"""
        return self._get("/api/v1/chat/sessions")

    def get_history(self, session_id: str) -> dict:
        """获取指定会话的历史消息"""
        return self._get(f"/api/v1/chat/history/{session_id}")

    # ========== 记忆管理 v2.0 ==========

    def memory_stats(self) -> dict:
        """获取记忆系统统计"""
        return self._get("/api/v1/memory/stats")

    # --- 会话语料 ---
    def get_corpus(self, date: str) -> dict:
        """获取指定日期的会话语料"""
        return self._get(f"/api/v1/memory/corpus/{date}")

    def list_corpus(self) -> dict:
        """获取所有会话语料"""
        return self._get("/api/v1/memory/corpus")

    # --- 索引 ---
    def search_index(self, query: str) -> dict:
        """搜索索引"""
        return self._get("/api/v1/memory/index/search", params={"query": query})

    def get_hot_entries(self, limit: int = 10) -> dict:
        """获取热门索引条目"""
        return self._get("/api/v1/memory/index/hot", params={"limit": limit})

    def get_index_stats(self) -> dict:
        """获取索引统计"""
        return self._get("/api/v1/memory/index/stats")

    # --- 每日日志 ---
    def read_daily_log(self, date: str) -> dict:
        """读取每日日志"""
        return self._get(f"/api/v1/memory/daily-log/{date}")

    def list_daily_logs(self) -> dict:
        """列出每日日志"""
        return self._get("/api/v1/memory/daily-logs")

    # --- 长期记忆 ---
    def read_long_term_memory(self) -> dict:
        """读取长期记忆"""
        return self._get("/api/v1/memory/long-term")

    def write_long_term_memory(self, content: str) -> dict:
        """写入长期记忆"""
        return self._post("/api/v1/memory/long-term", {"content": content})

    def append_long_term_memory(self, content: str) -> dict:
        """追加到长期记忆"""
        return self._post("/api/v1/memory/long-term/append", {"content": content})

    def extract_long_term_memory(self) -> dict:
        """手动提取到长期记忆"""
        return self._post("/api/v1/memory/long-term/extract")

    # --- 记忆检索 ---
    def search_memory(self, query: str, corpus: str = "all") -> dict:
        """记忆全局搜索"""
        return self._get("/api/v1/memory/search", params={"query": query, "corpus": corpus})

    # ========== 删除功能 ==========

    def delete_session(self, session_id: str) -> dict:
        """删除指定会话"""
        return self._delete(f"/api/v1/chat/session/{session_id}")

    def clear_all_sessions(self) -> dict:
        """清空所有会话"""
        return self._delete("/api/v1/chat/sessions")

    def delete_daily_log(self, date: str) -> dict:
        """删除每日日志"""
        return self._delete(f"/api/v1/memory/daily-log/{date}")

    def delete_long_term_memory(self) -> dict:
        """清空长期记忆"""
        return self._delete("/api/v1/memory/long-term")

    def clear_corpus(self) -> dict:
        """清空会话语料"""
        return self._delete("/api/v1/memory/corpus")

    def clear_index(self) -> dict:
        """清空索引"""
        return self._delete("/api/v1/memory/index")

    def clear_all_memory(self) -> dict:
        """清空所有记忆"""
        return self._delete("/api/v1/memory/all")

    # ========== 技能管理 ==========

    def list_skills(self) -> dict:
        """列出所有技能"""
        return self._get("/api/v1/skills/")

    def reload_skills(self) -> dict:
        """重新加载技能"""
        return self._post("/api/v1/skills/reload")

    def get_skill(self, name: str) -> dict:
        """获取技能详情"""
        return self._get(f"/api/v1/skills/{name}")

    def create_skill(self, name: str, code: str) -> dict:
        """创建新技能"""
        return self._post("/api/v1/skills/", {"name": name, "code": code})

    def delete_skill(self, name: str) -> dict:
        """删除技能"""
        return self._delete(f"/api/v1/skills/{name}")

    def execute_skill(self, name: str, params: dict = None) -> dict:
        """执行技能"""
        return self._post("/api/v1/skills/execute", {"name": name, "params": params or {}})

    def match_skill(self, question: str) -> dict:
        """匹配技能"""
        return self._post("/api/v1/skills/match", {"question": question})

    def get_skill_template(self) -> dict:
        """获取技能模板"""
        return self._get("/api/v1/skills/template/default")


@st.cache_resource
def get_api_client(backend_url: str = "http://localhost:8000") -> APIClient:
    """获取 API 客户端单例（带 Streamlit 缓存）"""
    return APIClient(base_url=backend_url)
