"""
聊天界面组件
提供对话展示和输入功能
"""
import streamlit as st
from typing import List, Dict
from api_client import APIClient


def init_chat_session():
    """初始化聊天会话状态"""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "session_id" not in st.session_state:
        st.session_state.session_id = None

    if "available_sessions" not in st.session_state:
        st.session_state.available_sessions = []


def render_session_selector(api_client):
    """渲染会话选择器（顶部）"""
    # 获取所有会话
    try:
        result = api_client.list_sessions()
        sessions = result.get("sessions", []) if result.get("code") == 200 else []
    except:
        sessions = []

    # 连接状态和会话控制放在顶部右侧
    col1, col2, col3 = st.columns([6, 1, 1])

    # 后端连接状态
    with col1:
        pass  # 左侧留空

    # 新建会话按钮
    with col2:
        if st.button("➕ 新建会话", use_container_width=True):
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()

    # 会话历史选择器
    with col3:
        if sessions:
            session_options = ["📋 历史会话"] + sessions
            selected = st.selectbox("", session_options, label_visibility="collapsed")
            if selected and selected != "📋 历史会话":
                st.session_state.session_id = selected
                st.session_state.messages = []
                st.rerun()


def render_chat_message(role: str, content: str, sources: List[Dict] = None):
    """
    渲染单条聊天消息
    Args:
        role: "user" 或 "assistant"
        content: 消息内容
        sources: 引用来源（仅assistant消息）
    """
    with st.chat_message(role):
        st.markdown(content)

        # 显示引用来源
        if sources and role == "assistant":
            with st.expander(f"📖 引用来源 ({len(sources)} 个文档)", expanded=False):
                for i, source in enumerate(sources):
                    st.markdown(f"**{i+1}. {source.get('doc_name', '未知文档')}**")
                    st.caption(f"相关性: {source.get('score', 0):.2%}")
                    st.text(source.get("content", "")[:300] + "...")
                    if i < len(sources) - 1:
                        st.divider()


def render_chat_input(api_client: APIClient, top_k: int = 5):
    """
    渲染聊天输入框并处理用户输入
    """
    if prompt := st.chat_input("请输入您的问题..."):
        # 添加用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # 调用后端 API
        with st.chat_message("assistant"):
            with st.spinner("正在检索文档并生成回答..."):
                result = api_client.chat(
                    query=prompt,
                    session_id=st.session_state.session_id,
                    top_k=top_k,
                )

            if result.get("code") == 200:
                answer = result.get("answer", "无法获取回答")
                sources = result.get("sources", [])
                session_id = result.get("session_id")

                # 保存会话ID
                if session_id:
                    st.session_state.session_id = session_id

                # 显示回答
                st.markdown(answer)

                # 显示引用来源
                if sources:
                    with st.expander(f"📖 引用来源 ({len(sources)} 个文档)", expanded=False):
                        for i, source in enumerate(sources):
                            st.markdown(f"**{i+1}. {source.get('doc_name', '未知文档')}**")
                            st.caption(f"相关性: {source.get('score', 0):.2%}")
                            st.text(source.get("content", "")[:300] + "...")
                            if i < len(sources) - 1:
                                st.divider()
                else:
                    st.caption("⚠️ 暂无相关文档内容，LLM基于通用知识回答")

                # 保存助手消息
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })
            else:
                error_msg = result.get("message", "请求失败")
                st.error(f"❌ {error_msg}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"❌ 出错了: {error_msg}",
                    "sources": [],
                })


def render_chat_history():
    """渲染历史聊天消息"""
    for msg in st.session_state.messages:
        # 兼容role和type两种格式
        role = msg.get("role") or msg.get("type", "user")
        with st.chat_message(role):
            st.markdown(msg["content"])

            # 显示历史消息中的引用来源
            if role == "assistant" and msg.get("sources"):
                with st.expander(f"📖 引用来源 ({len(msg['sources'])} 个文档)", expanded=False):
                    for i, source in enumerate(msg["sources"]):
                        st.markdown(f"**{i+1}. {source.get('doc_name', '未知文档')}**")
                        st.caption(f"相关性: {source.get('score', 0):.2%}")
                        st.text(source.get("content", "")[:300] + "...")
                        if i < len(msg['sources']) - 1:
                            st.divider()


def render_clear_chat_button():
    """渲染清空对话按钮"""
    col1, col2, col3 = st.columns([3, 1, 3])
    with col2:
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = None
            st.rerun()
