"""
侧边栏组件
提供文件上传和文档管理入口
"""
from collections import Counter

import streamlit as st
from api_client import APIClient


def render_sidebar(api_client: APIClient):
    """渲染侧边栏"""
    with st.sidebar:

        # ========== 会话历史列表（类似DeepSeek风格）==========
        st.divider()
        st.subheader("💬 会话历史")
        
        # 新建会话按钮
        if st.button("➕ 新建会话", use_container_width=True, key="new_session_btn"):
            st.session_state.session_id = None
            st.session_state.messages = []
            # 重置 selectbox 选择为默认项
            st.session_state["session_select"] = "-- 选择会话 --"
            st.rerun()
        
        # 获取历史会话列表
        result = api_client.list_sessions()
        # 兼容有无code字段的情况
        sessions = result.get("sessions", []) if result.get("code", 200) == 200 else []
        if not sessions and "sessions" in result:
            sessions = result.get("sessions", [])
        
        # 使用selectbox选择会话
        if sessions:
            # 收集所有 (sid, title) 对
            session_pairs = []
            for s in sessions:
                if isinstance(s, dict):
                    sid = s.get("id", "")
                    title = s.get("title", sid[:8])
                else:
                    sid = s
                    title = s[:8]
                session_pairs.append((sid, title))

            # 统计标题出现次数，用于区分同名会话
            title_counts = Counter(t for _, t in session_pairs)

            # 构建选项列表：同名会话追加 sid 前缀以区分
            session_map = {"-- 选择会话 --": ""}
            for sid, title in session_pairs:
                if title_counts[title] > 1:
                    label = f"{title}  [{sid[:8]}]"
                else:
                    label = title
                session_map[label] = sid

            session_options = list(session_map.keys())
            selected_title = st.selectbox("选择历史会话", session_options, label_visibility="collapsed", key="session_select")
            selected_id = session_map.get(selected_title, "")

            if selected_id:
                # 只有当选择的会话与当前不同时才加载
                current = st.session_state.get("session_id")
                if current != selected_id:
                    st.session_state.session_id = selected_id
                    # 获取该会话的历史消息
                    history_result = api_client.get_history(selected_id)
                    history = history_result.get("history", []) if history_result.get("code") == 200 else []
                    # 转换为messages格式
                    messages = []
                    for msg in history:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        if role == "user":
                            messages.append({"type": "user", "content": content})
                        elif role == "assistant":
                            messages.append({"type": "assistant", "content": content})
                    st.session_state.messages = messages
                    st.rerun()

            # 删除当前会话按钮
            current_session = st.session_state.get("session_id")
            if current_session:
                # 检查当前会话是否在列表中
                current_in_list = any(
                    (isinstance(s, dict) and s.get("id") == current_session) or s == current_session
                    for s in sessions
                )
                if current_in_list:
                    if st.button("🗑️ 删除当前会话", use_container_width=True, key="del_session_btn"):
                        res = api_client.delete_session(current_session)
                        if res.get("code") == 200:
                            st.session_state.session_id = None
                            st.session_state.messages = []
                            if "session_select" in st.session_state:
                                del st.session_state["session_select"]
                            st.success("会话已删除")
                            st.rerun()
                        else:
                            st.error("删除失败")
        else:
            st.caption("暂无会话历史")

        st.divider()

        # ========== 上传文档 ==========
        st.subheader("📤 上传文档")
        
        # 初始化上传状态
        if "_uploading_file" not in st.session_state:
            st.session_state._uploading_file = None
            
        uploaded_file = st.file_uploader(
            "支持 Word / PDF / 图片 / 文本",
            type=["pdf", "docx", "doc", "txt", "md", "jpg", "jpeg", "png", "bmp"],
            key="doc_file_uploader",
        )
        
        if uploaded_file is not None:
            st.caption(f"已选择: {uploaded_file.name}")
            if st.button("🚀 上传", key="upload_btn"):
                if st.session_state.get("_uploading_file") == uploaded_file.name:
                    st.warning("文件正在上传中...")
                else:
                    st.session_state._uploading_file = uploaded_file.name
                    with st.spinner(f"正在上传 {uploaded_file.name}..."):
                        result = api_client.upload_file(
                            file_bytes=uploaded_file.getvalue(),
                            filename=uploaded_file.name,
                        )
                    
                    if result.get("code") == 200:
                        doc = result.get("document", {})
                        st.success(f"✅ {doc.get('filename', uploaded_file.name)} 上传成功")
                        st.session_state._uploading_file = None
                    else:
                        st.error(f"❌ 上传失败: {result.get('message', '未知错误')}")
                        st.session_state._uploading_file = None

        st.divider()

        # ========== 文档列表 ==========
        st.subheader("📋 已上传文档")
        
        result = api_client.list_documents(page_size=50)
        
        if result.get("code") == 200:
            docs = result.get("data", [])
            if docs:
                for doc in docs:
                    col1, col2 = st.sidebar.columns([4, 1])
                    with col1:
                        filename = doc.get("filename", doc.get("doc_id", "未知"))
                        chunks = doc.get("chunk_count", 0)
                        st.caption(f"📄 {filename[:15]}... ({chunks}块)")
                    with col2:
                        if st.button("🗑️", key=f"del_{doc['doc_id']}", help=f"删除 {filename}"):
                            del_result = api_client.delete_document(doc["doc_id"])
                            if del_result.get("code") == 200:
                                st.success("已删除")
                                st.rerun()
                            else:
                                st.error("删除失败")
            else:
                st.caption("暂无文档")
        else:
            st.caption("获取文档失败")

        # ========== 检索设置 ==========
        st.divider()
        st.subheader("⚙️ 检索设置")
        top_k = st.slider(
            "Top-K",
            min_value=1,
            max_value=20,
            value=5,
            help="返回最相关的K个文档块"
        )

        return {
            "top_k": top_k,
        }


def render_document_list_sidebar(api_client: APIClient):
    """渲染文档列表（备用）"""
    pass
