# RAG 智能问答系统

基于文档检索增强生成（RAG）的智能问答系统，支持文档管理、分层记忆系统和自定义技能插件。

## 功能特性

### 智能问答
- 基于上传文档的 RAG 检索增强问答
- 支持多轮对话，自动维护会话历史
- 混合检索策略（BM25F + FAISS + RRF 融合）
- 智能路由：自动判断是否需要检索文档或调用技能

### 文档管理
- 支持 PDF、Word、图片、文本等多种格式上传
- 文档自动分块与向量化索引
- 文档详情查看，支持按文本块浏览内容
- 已上传文档列表管理与删除

### 记忆管理系统 v2.0
- **会话语料**：自动记录每日对话历史
- **短期索引**：关键词索引，快速检索
- **每日日志**：自动压缩与整理
- **长期记忆**：LLM 驱动的人物画像结构化提取

### 技能工坊
- 内置技能：天气查询、计算器等
- 支持自定义 Agent 技能插件
- 技能通过关键词触发，扩展 AI 能力

## 技术架构

| 层级 | 技术 |
|------|------|
| 前端 | Streamlit |
| 后端 | FastAPI + Uvicorn |
| 向量库 | FAISS |
| 嵌入模型 | DashScope text-embedding-v2 |
| LLM | MiniMax-M2.5 |
| 关键词检索 | BM25F + jieba 中文分词 |

## 快速开始

### 环境要求
- Python 3.12+

### 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd frontend
pip install -r requirements.txt
```

### 配置环境变量

在 `backend/.env` 中配置 API 密钥：

```env
DASHSCOPE_API_KEY=your_dashscope_key
MINIMAX_API_KEY=your_minimax_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
```

### 启动服务

```bash
# 启动后端（端口 8000）
cd backend
python run.py

# 启动前端（端口 8501）
cd frontend
streamlit run app.py
```

访问 http://localhost:8501 即可使用。

## 项目结构

```
.
├── backend/              # 后端服务
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── models/       # 数据模型
│   │   ├── services/     # 业务逻辑
│   │   │   ├── rag_service.py      # RAG 核心服务
│   │   │   ├── vector_store.py     # 向量存储
│   │   │   ├── embedding_service.py # 嵌入服务
│   │   │   ├── memory_service.py   # 记忆系统
│   │   │   └── skill_manager.py    # 技能管理
│   │   └── config.py     # 配置
│   ├── skills/           # 内置技能
│   ├── uploads/          # 上传文档
│   └── vector_db/        # 向量数据库
├── frontend/             # 前端界面
│   ├── pages/            # 页面
│   │   ├── chat.py       # 智能问答
│   │   ├── manage.py     # 文档管理
│   │   ├── memory.py     # 记忆系统
│   │   └── skills.py     # 技能工坊
│   └── components/       # 组件
└── .qoder/skills/        # Agent 技能
```

## 界面预览

### 智能问答
支持基于文档的上下文问答，自动显示引用来源。

### 文档管理
上传、查看、管理知识库文档，支持文本块级详情浏览。

### 记忆管理系统
分层记忆架构：会话语料 → 短期索引 → 长期记忆。

### 技能工坊
创建自定义 Python 技能，通过关键词触发扩展 AI 能力。

## 开源协议

MIT License
