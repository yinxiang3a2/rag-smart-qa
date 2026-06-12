---
name: code-standards
description: 本项目代码编写规范。当修改或新增代码时使用，包含 MiniMax API 调用、Streamlit 配置、代理处理、文档解析、向量库使用等关键约定。
---

# 代码编写规范

## 核心原则

1. 修改前先 `Read` 确认内容，不要猜测行号
2. 用 `SearchReplace` 精确修改，每次不超过 600 行原始文本
3. 修改完成后用 `GetProblems` 检查语法

## 必检规范

| 检查项 | 规则 |
|--------|------|
| SOCKS 代理 | 外部 API 调用文件必须清除 `all_proxy` |
| bare except | 禁止使用 `except:`，用 `except Exception:` |
| Streamlit | `set_page_config` 只能放在 `frontend/app.py` 中调用一次 |

运行自动检查：
```bash
python scripts/check_syntax.py <文件路径>
```

## 详细参考

所有 API 调用示例和代码模板见 [reference.md](reference.md)

- MiniMax 嵌入 API（非 OpenAI 格式）
- MiniMax LLM API（OpenAI 兼容格式）
- SOCKS 代理清除
- PDF/Word 文档解析
- FAISS 向量存储

## Python 环境

- 版本：**3.12+**
- 虚拟环境：`/home/10359121/10359121/pro2/.venv`
- 启动后端：`cd backend && python run.py`
- 启动前端：`streamlit run app.py --server.port 8501`
