"""
Streamlit 前端主入口
启动命令: streamlit run app.py
"""
import streamlit as st

# 设置页面配置（必须是第一个 Streamlit 命令）
st.set_page_config(
    page_title="RAG 智能问答系统",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
)

# 自适应页面样式
st.markdown("""
<style>
    /* 小屏幕自动调整侧边栏 */
    @media (max-width: 768px) {
        section[data-testid="stSidebar"] {
            width: 250px !important;
        }
    }
    /* 主内容区自适应 */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    /* 聊天气泡自适应 */
    .stChatMessage {
        padding: 0.5rem 0.8rem;
    }
    /* 移动端隐藏多余间距 */
    @media (max-width: 480px) {
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# 导入并运行聊天页面
from pages.chat import main

if __name__ == "__main__":
    main()
