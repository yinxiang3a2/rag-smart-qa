"""
文档管理页面
查看和管理已上传的文档
"""
import streamlit as st
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import APIClient, get_api_client
from components.sidebar import render_sidebar, render_document_list_sidebar


def main():
    """文档管理页面主函数"""

    api_client = get_api_client()

    # 侧边栏
    render_sidebar(api_client)

    st.title("📋 文档管理")
    st.caption("查看和管理已上传的知识库文档")

    # 获取文档列表
    result = api_client.list_documents(page_size=100)

    if result.get("code") == 200:
        docs = result.get("data", [])

        if docs:
            # 构建表格数据
            table_data = []
            for doc in docs:
                table_data.append({
                    "文档ID": doc.get("doc_id", ""),
                    "文件名": doc.get("filename", "未知"),
                    "类型": doc.get("ext", "").upper(),
                    "文本块数": doc.get("chunk_count", 0),
                })

            df = pd.DataFrame(table_data)

            # 显示表格
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(f"共 {len(docs)} 个文档")

            # 文档详情区域
            st.divider()
            st.subheader("🔍 文档详情")

            # 选择文档查看详情
            doc_options = {doc.get("filename", doc["doc_id"]): doc["doc_id"] for doc in docs}
            selected_name = st.selectbox(
                "选择文档查看详情",
                options=list(doc_options.keys()),
            )

            if selected_name:
                doc_id = doc_options[selected_name]
                detail = api_client.get_document(doc_id)

                if detail.get("code") == 200:
                    data = detail.get("data", {})
                    chunks = data.get("chunks", [])
                    total_chunks = data.get("total_chunks", len(chunks))

                    # 文档信息卡片
                    st.markdown("""
                    <style>
                    .doc-detail-card {
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 1.5rem;
                        border-radius: 12px;
                        color: white;
                        margin-bottom: 1rem;
                    }
                    .doc-detail-card h4 {
                        margin: 0 0 0.5rem 0;
                        font-size: 1.2rem;
                    }
                    .doc-detail-card .meta {
                        opacity: 0.9;
                        font-size: 0.9rem;
                    }
                    .chunk-card {
                        background: #f8f9fa;
                        border-left: 4px solid #667eea;
                        padding: 1rem;
                        border-radius: 0 8px 8px 0;
                        margin-bottom: 0.8rem;
                    }
                    .chunk-header {
                        font-weight: 600;
                        color: #495057;
                        margin-bottom: 0.5rem;
                    }
                    .chunk-content {
                        color: #6c757d;
                        line-height: 1.6;
                        white-space: pre-wrap;
                    }
                    </style>
                    """, unsafe_allow_html=True)

                    # 文档概览卡片
                    st.markdown(f"""
                    <div class="doc-detail-card">
                        <h4>📄 {selected_name}</h4>
                        <div class="meta">文档 ID: {doc_id} | 文本块数: {total_chunks}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    if not chunks:
                        st.info("该文档暂无文本块内容")
                    else:
                        st.caption(f"共 {total_chunks} 个文本块，点击展开查看内容")

                        # 显示文本块
                        for i, chunk in enumerate(chunks, 1):
                            with st.expander(
                                f"📝 文本块 {i} / {total_chunks}",
                                expanded=False
                            ):
                                content = chunk.get("content", "")
                                if content:
                                    st.markdown(f"""
                                    <div class="chunk-card">
                                        <div class="chunk-content">{content}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    st.caption("（空内容）")

                                # 显示元数据
                                chunk_id = chunk.get("chunk_id", "")
                                created_at = chunk.get("created_at", "")
                                if chunk_id or created_at:
                                    cols = st.columns(2)
                                    with cols[0]:
                                        st.caption(f"ID: `{chunk_id}`")
                                    with cols[1]:
                                        st.caption(f"创建: {created_at}")

                elif detail.get("code") == 404:
                    st.warning("⚠️ 该文档不存在或已被删除")
                elif detail.get("code") == 503:
                    st.error("🔌 无法连接到后端服务，请确保后端已启动")
                else:
                    error_msg = detail.get("message", "未知错误")
                    st.error(f"❌ 获取文档详情失败: {error_msg}")

            # 批量删除区域
            st.divider()
            st.subheader("🗑️ 删除文档")

            doc_to_delete = st.multiselect(
                "选择要删除的文档",
                options=list(doc_options.keys()),
            )

            if doc_to_delete and st.button("确认删除所选文档", type="primary"):
                for name in doc_to_delete:
                    doc_id = doc_options[name]
                    del_result = api_client.delete_document(doc_id)
                    if del_result.get("code") == 200:
                        st.success(f"已删除: {name}")
                    else:
                        st.error(f"删除失败: {name}")

                st.rerun()
        else:
            st.info("📭 暂无已上传的文档")
            st.caption("请通过侧边栏或聊天页面上传文档")
    else:
        st.error(f"获取文档列表失败: {result.get('message', '未知错误')}")


if __name__ == "__main__":
    main()

