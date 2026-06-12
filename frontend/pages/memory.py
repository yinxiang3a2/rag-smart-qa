"""
记忆管理页面 v2.0
管理分层记忆系统：会话语料、短期记忆索引、长期记忆
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import get_api_client


def render_memory_stats(api_client):
    """渲染记忆统计"""
    result = api_client.memory_stats()
    if result.get("code") == 200:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("会话语料", result.get("corpus_count", 0))
        with col2:
            st.metric("索引条目", result.get("index_entries", 0))
        with col3:
            st.metric("每日日志", result.get("daily_logs_count", 0))
        with col4:
            has_lt = "✅" if result.get("long_term_exists") else "❌"
            st.metric("长期记忆", has_lt)


def render_corpus(api_client):
    """渲染会话语料管理"""
    st.subheader("📝 会话语料")
    
    # 获取所有语料
    result = api_client.list_corpus()
    corpus_list = result.get("corpus", []) if result.get("code") == 200 else []
    
    if corpus_list:
        st.info(f"共 {len(corpus_list)} 个会话语料文件")
        
        # 选择日期
        date_options = [c.get("date", "") for c in corpus_list]
        selected_date = st.selectbox("选择日期", date_options, key="corpus_select")
        
        if selected_date:
            corpus_result = api_client.get_corpus(selected_date)
            if corpus_result.get("code") == 200:
                entries = corpus_result.get("entries", [])
                st.write(f"共 {len(entries)} 条对话记录")
                
                # 显示对话列表
                for entry in entries[:50]:
                    role = entry.get("role", "")
                    text = entry.get("text", "")
                    timestamp = entry.get("timestamp", "")
                    
                    if role == "USER":
                        st.markdown(f"**[{timestamp}] 用户**: {text}")
                    else:
                        st.markdown(f"~~[{timestamp}] AI~~: {text[:100]}{'...' if len(text) > 100 else ''}")
                        st.divider()
    else:
        st.caption("暂无会话语料。请先进行对话，系统会自动记录。")


def render_index(api_client):
    """渲染短期记忆索引"""
    st.subheader("🔍 短期记忆索引")
    
    # 索引统计
    stats = api_client.get_index_stats()
    if stats.get("code") == 200:
        st.write(f"索引条目: {stats.get('totalEntries', 0)}")
        
        # 热门标签
        top_tags = stats.get("topTags", [])
        if top_tags:
            st.write("**热门标签**:")
            tags_str = ", ".join([f"{tag[0]} ({tag[1]})" for tag in top_tags[:10]])
            st.caption(tags_str)
    
    # 搜索索引
    query = st.text_input("搜索索引", key="index_search")
    if query and st.button("搜索", key="search_index_btn"):
        resp = api_client.search_index(query)
        results = resp.get("results", []) if resp.get("code") == 200 else []
        if results:
            st.write(f"找到 {len(results)} 条结果:")
            for r in results[:10]:
                st.markdown(f"- **{r.get('key', '')}** (召回: {r.get('recallCount', 0)})")
                st.caption(f"标签: {', '.join(r.get('conceptTags', []))}")
        else:
            st.caption("未找到匹配结果")
    
    # 热门条目
    st.divider()
    st.write("**热门条目 (按召回次数)**")
    hot_result = api_client.get_hot_entries(limit=10)
    hot = hot_result.get("entries", []) if hot_result.get("code") == 200 else []
    if hot:
        for i, entry in enumerate(hot, 1):
            st.markdown(f"{i}. {entry.get('key', '')}")
            st.caption(f"召回: {entry.get('recallCount', 0)} | 标签: {', '.join(entry.get('conceptTags', []))}")
    else:
        st.caption("暂无索引条目")


def render_long_term_memory(api_client):
    """渲染长期记忆管理"""
    st.subheader("🧠 长期记忆 (用户画像)")
    
    # 读取长期记忆
    result = api_client.read_long_term_memory()
    if result.get("code") == 200:
        current_content = result.get("content", "")
        
        # 手动提取到长期记忆（新功能）
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("#### 🎯 从记忆数据提取")
            st.caption("从索引条目和会话语料中整合提取，生成用户画像（手动触发）")
        with col2:
            if st.button("🚀 提取到长期记忆", key="extract_to_long_term"):
                with st.spinner("正在提取..."):
                    res = api_client.extract_long_term_memory()
                if res.get("code") == 200:
                    st.success("✅ 长期记忆已更新！")
                    st.rerun()
                else:
                    st.error(f"提取失败: {res.get('message', '未知错误')}")
        
        st.divider()
        
        # 编辑长期记忆
        with st.expander("✏️ 编辑长期记忆"):
            new_content = st.text_area("内容", value=current_content, height=300)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("覆盖保存", key="overwrite_lt"):
                    res = api_client.write_long_term_memory(new_content)
                    if res.get("code") == 200:
                        st.success("已保存")
                        st.rerun()
            with c2:
                if st.button("追加内容", key="append_lt"):
                    res = api_client.append_long_term_memory(new_content)
                    if res.get("code") == 200:
                        st.success("已追加")
                        st.rerun()
        
        # 显示当前内容
        with st.expander("📖 查看当前内容", expanded=True):
            st.markdown(current_content if current_content.strip() else "*暂无内容*")
        
        # 清空长期记忆
        with st.expander("⚠️ 危险操作"):
            if st.button("🗑️ 清空长期记忆", key="clear_lt"):
                res = api_client.delete_long_term_memory()
                if res.get("code") == 200:
                    st.success("长期记忆已清空")
                    st.rerun()
                else:
                    st.error("清空失败")


def render_memory_search(api_client):
    """渲染记忆搜索"""
    st.subheader("🔍 记忆全局搜索")
    
    query = st.text_input("搜索关键词", key="memory_search_query")
    corpus = st.selectbox(
        "搜索范围",
        ["all", "corpus", "index", "daily", "longterm"],
        format_func=lambda x: {
            "all": "全部",
            "corpus": "会话语料",
            "index": "索引",
            "daily": "每日日志",
            "longterm": "长期记忆"
        }.get(x, x)
    )
    
    if st.button("搜索", key="search_memory_btn") and query:
        with st.spinner("搜索中..."):
            result = api_client.search_memory(query, corpus)
        
        if result.get("code") == 200:
            data = result.get("results", {})
            
            # 会话语料结果
            corpus_results = data.get("corpus", [])
            if corpus_results:
                st.write("**📝 会话语料**")
                for item in corpus_results[:5]:
                    with st.expander(f"📅 {item.get('date', '')}"):
                        st.text(item.get("snippet", ""))
            
            # 索引结果
            index_results = data.get("index", [])
            if index_results:
                st.write("**🔍 索引**")
                for item in index_results[:5]:
                    st.markdown(f"- {item.get('key', '')} (召回: {item.get('recallCount', 0)})")
            
            # 每日日志结果
            daily_results = data.get("daily", [])
            if daily_results:
                st.write("**📅 每日日志**")
                for item in daily_results[:5]:
                    with st.expander(f"📅 {item.get('date', '')}"):
                        st.text(item.get("snippet", ""))
            
            # 长期记忆结果
            lt_results = data.get("longterm", [])
            if lt_results:
                st.write("**🧠 长期记忆**")
                for item in lt_results[:5]:
                    st.info(item.get("snippet", ""))
            
            if not any([corpus_results, index_results, daily_results, lt_results]):
                st.caption("未找到相关记忆")
        else:
            st.error("搜索失败")


def main():
    """记忆管理页面主函数"""
    st.title("🧠 记忆管理系统 v2.0")
    st.caption("分层记忆：会话语料 → 短期索引 → 长期记忆")
    
    api_client = get_api_client()
    
    # 统计概览
    render_memory_stats(api_client)
    
    # 全局危险操作
    with st.expander("⚠️ 全局危险操作"):
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🗑️ 清空会话语料", key="clear_corpus"):
                res = api_client.clear_corpus()
                if res.get("code") == 200:
                    st.success("会话语料已清空")
                    st.rerun()
        with col2:
            if st.button("🗑️ 清空索引", key="clear_index"):
                res = api_client.clear_index()
                if res.get("code") == 200:
                    st.success("索引已清空")
                    st.rerun()
        with col3:
            if st.button("🗑️ 清空所有记忆", key="clear_all"):
                res = api_client.clear_all_memory()
                if res.get("code") == 200:
                    st.success("所有记忆已清空")
                    st.rerun()
    
    st.divider()
    
    # 标签页
    tab1, tab2, tab3, tab4 = st.tabs(["📝 会话语料", "🔍 短期索引", "🧠 长期记忆", "🔎 搜索"])
    
    with tab1:
        render_corpus(api_client)
    
    with tab2:
        render_index(api_client)
    
    with tab3:
        render_long_term_memory(api_client)
    
    with tab4:
        render_memory_search(api_client)


if __name__ == "__main__":
    main()
