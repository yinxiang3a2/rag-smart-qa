"""
智能问答页面
Streamlit 聊天界面
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import APIClient, get_api_client
from components.sidebar import render_sidebar
from components.chat_ui import (
    init_chat_session,
    render_chat_history,
    render_chat_input,
    render_clear_chat_button,
)


def main():
    """聊天页面主函数"""

    api_client = get_api_client()

    # 侧边栏：包含连接状态、会话历史、上传、文档列表
    settings = render_sidebar(api_client)
    top_k = settings.get("top_k", 5)

    # 初始化聊天会话
    init_chat_session()

    # 顶部标题
    st.title("🤖 RAG 智能问答")
    st.caption("基于文档检索增强生成的智能问答")

    # 清空对话按钮
    render_clear_chat_button()

    # 渲染历史消息
    render_chat_history()

    # 渲染输入框
    render_chat_input(api_client, top_k=top_k)


if __name__ == "__main__":
    main()
