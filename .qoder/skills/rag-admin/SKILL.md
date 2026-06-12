---
name: rag-admin
description: RAG 智能问答系统的管理和运维技能。当用户询问已上传文档、文档列表、重置向量库、清空索引、查看系统状态、删除指定文档、重启服务时触发。
---

# RAG 文档问答系统管理

## 系统架构

- **后端**: FastAPI，`http://localhost:8000`，向量库 FAISS
- **前端**: Streamlit，`http://localhost:8501`
- **嵌入模型**: MiniMax embo-01（1536维）
- **LLM模型**: MiniMax-M2.5
- **相似度阈值**: 0.3

## 脚本操作

所有管理操作通过 `scripts/` 目录下的脚本执行。

### 查看系统状态

```bash
python scripts/check_status.py
```

### 测试检索效果

```bash
python scripts/test_search.py "你的测试问题"
# 示例
python scripts/test_search.py "登录功能测试"
```

### 重启服务

```bash
# 重启全部（后端+前端）
python scripts/restart.py all

# 仅重启后端
python scripts/restart.py backend

# 仅重启前端
python scripts/restart.py frontend
```

## 元问题处理

以下问题不走向量检索，直接查文档列表：

- "我上传了什么"
- "有哪些文档"
- "文档列表"
- "索引了哪些文档"

## 已知限制

1. FAISS 数据持久化在 `vector_db/faiss.index`，重启后自动加载
2. PDF 文本提取优先 PyMuPDF，备选 pdfplumber
3. 嵌入类型统一使用 `type="db"`，保证向量空间一致
