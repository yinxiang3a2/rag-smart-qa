"""
技能管理页面
让用户自定义Agent技能
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_client import get_api_client


def render_skill_list(api_client):
    """渲染技能列表"""
    result = api_client.list_skills()
    skills = result.get("skills", []) if result.get("code") == 200 else []
    
    if skills:
        st.write(f"**已加载 {len(skills)} 个技能**")
        for skill in skills:
            with st.expander(f"🔧 {skill.get('name', '未命名')}"):
                st.write(f"**描述**: {skill.get('description', '无')}")
                st.write(f"**触发词**: {', '.join(skill.get('trigger_words', []))}")
                st.write(f"**参数**:")
                for param in skill.get('params', []):
                    req = "必填" if param.get('required') else f"可选(默认: {param.get('default')})"
                    st.write(f"  - `{param.get('name')}`: {req}")
                
                # 删除按钮
                if st.button("🗑️ 删除技能", key=f"del_skill_{skill['name']}"):
                    res = api_client.delete_skill(skill['name'])
                    if res.get("code") == 200:
                        st.success("技能已删除")
                        st.rerun()
                    else:
                        st.error("删除失败")
    else:
        st.caption("暂无自定义技能")
    
    # 刷新按钮
    if st.button("🔄 刷新技能列表"):
        api_client.reload_skills()
        st.rerun()


def render_create_skill(api_client):
    """渲染创建技能界面"""
    st.subheader("➕ 创建新技能")
    
    # 获取模板
    template_result = api_client.get_skill_template()
    example = template_result.get("example", "") if template_result.get("code") == 200 else ""
    
    # 显示示例
    with st.expander("📖 查看示例技能代码"):
        st.code(example, language="python")
    
    # 技能名称
    skill_name = st.text_input("技能文件名（英文，如: calculator）", "my_skill")
    
    # 代码编辑器
    default_code = '''"""
我的自定义技能
"""

SKILL_NAME = "我的技能"
SKILL_DESCRIPTION = "这是一个自定义技能"
SKILL_TRIGGER = ["关键词1", "关键词2"]

def run(input_text: str = ""):
    """
    技能执行函数
    
    参数:
        input_text: 用户输入
    
    返回:
        str: 执行结果
    """
    # 在这里写你的逻辑
    return f"处理结果: {input_text}"
'''
    skill_code = st.text_area("技能代码 (Python)", value=default_code, height=400)
    
    # 创建按钮
    if st.button("💾 保存技能", use_container_width=True):
        if skill_name.strip() and skill_code.strip():
            with st.spinner("创建技能中..."):
                res = api_client.create_skill(skill_name, skill_code)
            if res.get("code") == 200:
                st.success(f"技能 {res.get('skill', {}).get('name', skill_name)} 创建成功！")
                st.rerun()
            else:
                st.error(f"创建失败: {res.get('error', '未知错误')}")
        else:
            st.warning("名称和代码不能为空")


def render_test_skill(api_client):
    """渲染测试技能界面"""
    st.subheader("🧪 测试技能")
    
    question = st.text_input("输入测试问题")
    
    if st.button("🔍 匹配技能") and question:
        result = api_client.match_skill(question)
        if result.get("matched"):
            skill = result.get("skill", {})
            st.success(f"匹配到技能: {skill.get('name')}")
            st.write(f"描述: {skill.get('description')}")
            
            # 执行技能
            if st.button("▶️ 执行技能"):
                exec_result = api_client.execute_skill(skill.get('name'), {"question": question})
                if exec_result.get("code") == 200:
                    st.info(f"结果: {exec_result.get('result')}")
                else:
                    st.error(f"执行失败: {exec_result.get('error')}")
        else:
            st.caption("没有匹配到技能")


def main():
    """技能管理页面主函数"""
    st.title("🔧 技能工坊")
    st.caption("自定义Agent技能，让AI更强大")
    
    api_client = get_api_client()
    
    # 标签页
    tab1, tab2, tab3 = st.tabs(["📋 技能列表", "➕ 创建技能", "🧪 测试技能"])
    
    with tab1:
        render_skill_list(api_client)
    
    with tab2:
        render_create_skill(api_client)
    
    with tab3:
        render_test_skill(api_client)
    
    # 使用说明
    with st.expander("📖 使用说明"):
        st.markdown("""
        ### 技能编写规范
        
        1. **元数据**（必须）:
           - `SKILL_NAME`: 技能名称
           - `SKILL_DESCRIPTION`: 技能描述
           - `SKILL_TRIGGER`: 触发关键词列表
        
        2. **执行函数**（必须）:
           - 函数名必须是 `run`
           - 可以接收任意参数
           - 返回字符串结果
        
        3. **示例**:
        ```python
        SKILL_NAME = "翻译"
        SKILL_DESCRIPTION = "中英文互译"
        SKILL_TRIGGER = ["翻译", "translate", "英文", "中文"]
        
        def run(text: str = "", target: str = "英文"):
            # 你的翻译逻辑
            return f"翻译结果: ..."
        ```
        
        ### 工作原理
        
        1. 用户提问时，系统检查是否匹配技能触发词
        2. 如果匹配，调用技能的 `run` 函数
        3. 将结果直接返回给用户
        """)


if __name__ == "__main__":
    main()
