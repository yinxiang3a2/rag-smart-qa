"""
RAG 智能问答系统 - 双层架构
├── 调度层 Route: 分析意图 → 判断技能 → 提取参数 → 返回指令
└── 回答层 Answer: 接收指令 → 执行技能 → 生成最终回答
"""
import logging
import os
import re
import requests
import signal
import subprocess
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum
import uuid

from dotenv import load_dotenv
from openai import OpenAI

from .vector_store import vector_store
from ..config import settings
from .memory_service import memory_search
from .skill_manager import match_skill, execute_skill

logger = logging.getLogger(__name__)

# ========== 环境配置 ==========
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

AMAP_KEY = os.getenv("AMAP_KEY", "")
_GEO_URL = "https://restapi.amap.com/v3/config/district"
_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"


# ========== 技能定义 ==========
class SkillType(Enum):
    NONE = "none"          # 无需技能
    WEATHER = "weather"    # 天气查询
    STATUS = "status"      # 系统状态
    TEST_SEARCH = "test_search"  # 测试检索
    RESTART = "restart"    # 重启服务


@dataclass
class RouteResult:
    """路由结果"""
    need_skill: bool = False          # 是否需要调用技能
    skill_type: SkillType = SkillType.NONE  # 技能类型
    skill_params: dict = None       # 技能参数
    raw_question: str = ""        # 原始问题
    context: str = ""            # 检索到的上下文


# ========== 调度层 Router ==========
# 简单规则驱动+LLM判断混合
_QUESTIONS = {
    "weather": r"天气|气温|下雨|下雪|晴天|阴天|刮风|湿度|冷|热",
    "status": r"系统状态|状态怎么样|运行状况",
    "test_search": r"测试检索|检索测试",
    "restart": r"重启(后端|前端|服务|全部)?",
}


def _extract_city(question: str) -> Optional[str]:
    """提取城市名"""
    cities = "北京|上海|广州|深圳|杭州|南京|武汉|成都|重庆|西安|天津|苏州|郑州|" \
            "长沙|沈阳|青岛|济南|大连|哈尔滨|长春|昆明|兰州|福州|厦门|宁波|无锡|" \
            "佛山|东莞|合肥|石家庄|南昌|贵阳|太原|南宁|海口|乌鲁木齐|呼和浩特"
    match = re.search(cities, question)
    return match.group() if match else None


def _route_question(question: str, has_docs: bool) -> RouteResult:
    """
    调度层：分析问题，决定是否调用技能
    """
    q = question.strip()

    # 检查是否匹配技能模式
    for skill_name, pattern in _QUESTIONS.items():
        if re.search(pattern, q):
            params = {}

            # 提取技能参数
            if skill_name == "weather":
                city = _extract_city(q)
                if city:
                    params = {"city": city}
                    return RouteResult(
                        need_skill=True,
                        skill_type=SkillType.WEATHER,
                        skill_params=params,
                        raw_question=q
                    )

            elif skill_name == "status":
                return RouteResult(need_skill=True, skill_type=SkillType.STATUS, skill_params={}, raw_question=q)

            elif skill_name == "test_search":
                # 提取测试关键词
                test_kw = re.sub(r"测试检索|检索测试|试试检��", "", q).strip() or "登录功能"
                params = {"query": test_kw, "top_k": 3}
                return RouteResult(need_skill=True, skill_type=SkillType.TEST_SEARCH, skill_params=params, raw_question=q)

            elif skill_name == "restart":
                target = re.search(r"重启(后端|前端|服务|全部)?", q)
                target = target.group(1) or "all"
                params = {"target": target}
                return RouteResult(need_skill=True, skill_type=SkillType.RESTART, skill_params=params, raw_question=q)

    # 默认走RAG或知识问答
    return RouteResult(need_skill=False, raw_question=q)


# ========== 技能执行 ==========
def _execute_skill(skill_type: SkillType, params: dict) -> Optional[dict]:
    """执行技能，返回结果"""
    os.environ.pop("all_proxy", None)
    os.environ.pop("ALL_PROXY", None)

    try:
        if skill_type == SkillType.WEATHER:
            return _get_weather(params.get("city", ""))

        elif skill_type == SkillType.STATUS:
            stats = vector_store.get_stats()
            return {
                "answer": f"【系统状态】\n  类型: {stats.get('store_type', 'faiss')}\n  文档数: {stats.get('total_documents', 0)}\n  向量块: {stats.get('total_chunks', 0)}",
                "sources": []
            }

        elif skill_type == SkillType.TEST_SEARCH:
            results = vector_store.search(query=params.get("query", ""), top_k=params.get("top_k", 3))
            lines = [f"【检索测试】{params.get('query', '')}", f"匹配: {len(results)}个"]
            return {"answer": "\n".join(lines), "sources": []}

        elif skill_type == SkillType.RESTART:
            target = params.get("target", "all")
            return {"answer": f"正在重启{target}...", "sources": []}

    except Exception as e:
        logger.error(f"技能执行失败: {e}")
        return {"answer": f"技能执行失败: {e}", "sources": []}

    return None


def _get_weather(city: str) -> dict:
    """获取城市天气"""
    # 地理编码
    geo_resp = requests.get(_GEO_URL, params={"keywords": city, "subdistrict": 0, "key": AMAP_KEY}, timeout=10)
    districts = geo_resp.json().get("districts", [])
    if not districts:
        return {"answer": f"未找到{city}", "sources": []}

    adcode = next((d["adcode"] for d in districts if d.get("level") == "city"), districts[0]["adcode"])

    # 天气查询
    weather_resp = requests.get(_WEATHER_URL, params={
        "city": adcode, "key": AMAP_KEY, "extensions": "all", "output": "JSON"
    }, timeout=10)
    data = weather_resp.json()
    casts = data.get("forecasts", [{}])[0].get("casts", [])

    if not casts:
        return {"answer": f"未查到{city}天气", "sources": []}

    week_map = {"1": "周一", "2": "周二", "3": "周三", "4": "周四", "5": "周五", "6": "周六", "7": "周日"}
    lines = [f"【{city}天气预报】"]
    for day in casts:
        lines.append(f"{day['date']}({week_map.get(day['week'], '周'+day['week'])}): "
                   f"☀️{day['dayweather']}{day['daytemp']}°C → 🌙{day['nightweather']}{day['nighttemp']}°C")

    return {"answer": "\n".join(lines), "sources": []}


# ========== 回答层 Answer ==========
class AnswerModel:
    """回答层：大语言模型"""

    def __init__(self):
        self._client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_API_URL)
        self.llm_model = settings.LLM_MODEL_NAME
        logger.info(f"AnswerModel初始完成，LLM: {self.llm_model}")

    def generate(self, question: str, context: str, has_docs: bool, skill_result: str = "", history: list = None, user_preferences: str = "") -> str:
        """生成最终回答"""
        # 构建系统提示
        system_parts = []
        if skill_result:
            system_parts.append(f"工具结果：{skill_result}")
        if has_docs:
            system_parts.append("根据文档内容回答。")
        
        # 注入用户偏好到系统提示
        if user_preferences:
            system_parts.append(f"\n【用户偏好/记忆】\n{user_preferences}\n请根据以上用户偏好调整回答风格和内容。")
        
        system_parts.append("你是智能问答助手。回答简洁准确。")
        system_prompt = "\n".join(system_parts)

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加历史对话
        if history:
            for msg in history:
                messages.append(msg)
        
        # 当前问题
        user_content = f"参考：{context}\n\n问题：{question}" if context else f"问题：{question}"
        messages.append({"role": "user", "content": user_content})

        try:
            response = self._client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            answer = response.choices[0].message.content
            # 去掉思考内容
            if "</think>" in answer:
                answer = answer.split("</think>")[1].strip()
            return answer
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return f"生成回答失败: {e}"


# ========== 主服务类 ==========
class RAGService:
    """
    RAG 智能问答系统 - 双层架构
    1. 调度层路由 2. 执行技能 3. 回答层生成
    """

    def __init__(self):
        self._router = _route_question
        self._answer = AnswerModel()
        logger.info("RAG服务(双层架构)已启动")

        # 元问题模式
        self._META_PATTERNS = [
            re.compile(r"上传了[些什]", re.I),
            re.compile(r"有哪些文档", re.I),
            re.compile(r"文档列表", re.I),
        ]

    def query(self, question: str, top_k: int = None, filters: Optional[dict] = None, session_id: str = None) -> dict:
        """主入口：双层处理"""
        if session_id is None:
            session_id = uuid.uuid4().hex[:12]

        # 获取会话历史
        history = get_conversation_history(session_id)

        # 获取文档状态
        stats = vector_store.get_stats()
        has_docs = stats.get('total_documents', 0) > 0

        # ===== 步骤1: 调度层 =====
        # 检测元问题
        is_meta = any(p.search(question) for p in self._META_PATTERNS)

        if is_meta:
            # 元问题：直接列文档
            docs = vector_store.get_all_documents()
            context = self._build_meta_context(docs, stats)
            user_preferences = self._get_user_preferences()
            answer = self._answer.generate(question, context, has_docs, history=history, user_preferences=user_preferences)
            # 保存到会话历史
            add_to_history(session_id, question, answer)
            return {"answer": answer, "sources": [], "session_id": session_id}

        # 普通问题：路由决定
        route = self._router(question, has_docs)

        # ===== 步骤2: 技能执行（内置技能）=====
        skill_result = ""
        if route.need_skill:
            skill_exec = _execute_skill(route.skill_type, route.skill_params or {})
            if skill_exec:
                skill_result = skill_exec.get("answer", "")
        
        # ===== 步骤2.5: 用户自定义技能匹配 =====
        custom_skill_result = ""
        try:
            matched_skill = match_skill(question)
            if matched_skill and not route.need_skill:
                # 提取参数（简单实现：尝试用问题作为参数）
                custom_result = matched_skill.execute(question=question)
                if custom_result.get("code") == 200:
                    custom_skill_result = f"【{matched_skill.name}】{custom_result.get('result', '')}"
        except Exception as e:
            logger.warning(f"自定义技能匹配失败: {e}")

        # ===== 步骤3: RAG检索 (BM25F + FAISS + RRF 混合检索) =====
        if not route.need_skill and has_docs:
            # 使用混合检索：BM25F关键词 + FAISS向量 + RRF融合
            chunks = vector_store.hybrid_search(
                query=question,
                top_k=top_k or settings.RAG_TOP_K,
                use_bm25f=True,
            )
            logger.info(f"[混合检索] 查询: {question[:30]}... 结果: {len(chunks)} 条")
            route.context = self._build_context(chunks)
        else:
            route.context = ""

        # ===== 步骤3.5: 记忆检索 =====
        memory_context = ""
        try:
            # 判断是否需要检索记忆：只有用户明确询问个人信息时才触发
            should_search_memory = self._should_use_memory(question)
            
            if should_search_memory:
                memory_result = memory_search(question, corpus="all")
                logger.info(f"[记忆调试] 检索结果: code={memory_result.get('code')}")
                if memory_result.get("code") == 200:
                    mem_data = memory_result.get("results", {})
                    mem_parts = []
                    
                    # 索引条目（最高优先级）
                    index_results = mem_data.get("index", [])
                    logger.info(f"[记忆调试] 索引命中: {len(index_results)} 条")
                    for item in index_results[:3]:
                        mem_parts.append(f"[记忆] {item.get('key', '')} (标签: {', '.join(item.get('conceptTags', []))})")
                    
                    # 会话语料
                    corpus_results = mem_data.get("corpus", [])
                    logger.info(f"[记忆调试] 语料命中: {len(corpus_results)} 条")
                    for item in corpus_results[:2]:
                        mem_parts.append(f"[对话 {item.get('date', '')}] {item.get('snippet', '')}")
                    
                    # 长期记忆
                    for item in mem_data.get("long_term", [])[:1]:
                        mem_parts.append(f"[长期记忆] {item.get('snippet', '')}")
                    
                    # 每日日志
                    for item in mem_data.get("daily", [])[:1]:
                        mem_parts.append(f"[日志 {item.get('date', '')}] {item.get('snippet', '')}")
                    
                    if mem_parts:
                        memory_context = "\n\n".join(mem_parts)
                        # 添加约束：记忆是关于用户的信息，不是AI自己的信息
                        constraint = (
                            "[重要约束] 下方记忆信息仅描述【对话用户】的背景。"
                            "当用户询问自身信息时使用，若询问AI助手则忽略。\n\n"
                        )
                        memory_context = constraint + memory_context
                        logger.info(f"[记忆调试] memory_context长度: {len(memory_context)}")
            else:
                logger.info(f"[记忆调试] 跳过记忆检索（非个人信息查询）")
        except Exception as e:
            logger.warning(f"记忆检索失败: {e}")

        # ===== 步骤4: 回答层生成 =====
        # 合并文档上下文、记忆上下文和自定义技能结果
        combined_context = route.context
        if memory_context:
            combined_context = f"【相关记忆】\n{memory_context}\n\n【文档内容】\n{route.context}" if route.context else f"【相关记忆】\n{memory_context}"
        
        # 获取用户偏好（注入系统提示）
        user_preferences = self._get_user_preferences()
        
        # 如果有自定义技能结果，直接返回（不经过LLM）
        if custom_skill_result:
            answer = custom_skill_result
        else:
            answer = self._answer.generate(
                route.raw_question,
                combined_context,
                has_docs,
                skill_result,
                history,
                user_preferences
            )

        # 来源
        sources = []
        if route.context:
            seen = set()
            for chunk in vector_store.search(question, top_k=3):
                if chunk["doc_id"] not in seen:
                    seen.add(chunk["doc_id"])
                    sources.append({
                        "doc_id": chunk["doc_id"],
                        "doc_name": chunk["metadata"].get("filename", chunk["doc_id"]),
                        "score": round(chunk["score"], 4),
                    })

        # 保存到会话历史
        add_to_history(session_id, question, answer)

        # ===== 步骤5: 自动记录到每日日志 =====
        try:
            # 记录日志
            self._auto_log_conversation(question, answer, session_id)
            
            # 检查是否需要压缩日志（每N轮）
            if settings.AUTO_MEMORY_ENABLED:
                current_count = self._get_total_message_count()
                interval = getattr(settings, 'AUTO_MEMORY_INTERVAL', 10)
                if current_count > 0 and current_count % interval == 0:
                    logger.info(f"[记忆调试] 达到阈值({current_count}条)，开始压缩日志")
                    self._compress_daily_log()
        except Exception as e:
            logger.warning(f"自动记录失败: {e}")

        return {"answer": answer, "sources": sources, "session_id": session_id}

    def _auto_log_conversation(self, question: str, answer: str, session_id: str):
        """
        自动记录对话到语料库和每日日志
        每次对话后自动追加，同时写入 corpus/ 和 daily/
        """
        from .memory_service import append_to_corpus, write_daily_log
        from datetime import datetime
        
        date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. 追加到会话语料库（用于索引和检索）
        append_to_corpus(date, question, answer)
        
        # 2. 写入每日日志（可读格式）
        log_content = f"**用户**: {question}\n\n**AI**: {answer[:200]}{'...' if len(answer) > 200 else ''}\n\n**会话**: {session_id[:8]}"
        write_daily_log(date, log_content)
        
        logger.info(f"对话已记录到语料库和每日日志")

    def _compress_daily_log(self):
        """
        每日日志LLM压缩 + 索引更新
        每隔N轮对话后，自动从会话语料中提取关键信息并添加到索引
        """
        try:
            from .memory_service import get_corpus_by_date, add_index_entry
            from datetime import datetime
            from .memory_service import search_index
            
            date = datetime.now().strftime("%Y-%m-%d")
            
            # 1. 获取今日语料
            result = get_corpus_by_date(date)
            if result.get("code") != 200:
                return
            
            entries = result.get("entries", [])
            if not entries:
                return
            
            # 2. 提取用户消息（可能包含关键信息）
            user_messages = [e for e in entries if e.get("role") == "USER"]
            if not user_messages:
                return
            
            # 合并用户消息用于分析
            combined_text = "\n".join([e.get("text", "") for e in user_messages[-10:]])
            
            # 3. 调用LLM提取关键信息和标签
            prompt = f"""从以下对话中提取关键信息，生成索引条目。

## 对话
{combined_text}

## 输出要求
输出JSON格式：
{{
  "key": "一句话概括用户的关键信息（如：用户是25岁程序员，喜欢Python）",
  "tags": ["标签1", "标签2", "标签3"],
  "important": true/false  // 是否有值得记忆的重要信息
}}

只输出JSON，不要其他内容。"""
            
            response = self._answer._client.chat.completions.create(
                model=self._answer.llm_model,
                messages=[
                    {"role": "system", "content": "你是专业的对话分析助手，擅长提取关键信息。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
            )
            
            llm_result = response.choices[0].message.content.strip()
            if "</think>" in llm_result:
                llm_result = llm_result.split("</think>")[1].strip()
            
            # 解析LLM输出
            try:
                import json
                parsed = json.loads(llm_result)
                if parsed.get("important"):
                    # 添加到索引
                    entry_key = add_index_entry(
                        corpus_date=date,
                        line_start=0,
                        line_end=len(entries),
                        key=parsed.get("key", ""),
                        tags=parsed.get("tags", [])
                    )
                    logger.info(f"[记忆调试] 索引条目已添加: {entry_key}")
            except json.JSONDecodeError:
                logger.warning(f"[记忆调试] LLM输出解析失败: {llm_result[:100]}")
            
        except Exception as e:
            logger.warning(f"[记忆调试] 日志压缩/索引失败: {e}")

    def extract_to_long_term_memory(self):
        """
        手动提取到长期记忆
        从索引条目和会话语料中整合提取，生成用户画像
        供用户手动调用（通过API或前端按钮）
        """
        try:
            from .memory_service import (
                read_long_term_memory, 
                write_long_term_memory,
                get_hot_entries,
                get_all_corpus
            )
            
            # 1. 读取现有画像
            existing = read_long_term_memory()
            existing_profile = existing.get("content", "") if existing.get("code") == 200 else ""
            
            # 2. 获取索引中的热门条目
            hot_entries = get_hot_entries(limit=20)
            hot_text = "\n".join([f"- {e.get('key', '')} (标签: {', '.join(e.get('conceptTags', []))})" for e in hot_entries])
            
            # 3. 获取最近会话语料
            corpus_list = get_all_corpus()[:7]  # 最近7天的语料
            corpus_text = ""
            for c in corpus_list:
                corpus_text += f"\n\n=== {c['date']} ===\n"
                # 提取对话片段
                lines = c['content'].split("\n")
                user_lines = [l for l in lines if "USER:" in l]
                corpus_text += "\n".join(user_lines[-20:])  # 每日前20条用户消息
            
            if not hot_text and not corpus_text:
                return {"code": 400, "message": "暂无记忆数据，请先进行对话"}
            
            prompt = f"""你是一个专业的用户画像分析师。请根据以下记忆数据，提取和更新用户画像。

## 任务
1. 如果已有画像，在现有基础上补充和修正
2. 如果没有画像，创建新的画像
3. 只保留有明确信息的部分
4. 保持客观，不要推测

## 现有画像
{existing_profile if existing_profile and existing_profile.strip() not in ("# 长期记忆", "# 用户画像", "") else "（暂无）"}

## 热门索引条目
{hot_text if hot_text else "（暂无）"}

## 会话语料
{ corpus_text if corpus_text else "（暂无）"}

## 输出格式
严格按以下模板输出（用Markdown格式）：

# 用户画像

## 1. 基础信息
- 姓名/代号：
- 性别：
- 年龄：
- 职业/身份：
- 居住城市：

## 2. 行为与习惯
- 数字设备：
- 娱乐方式：
- 消费习惯：

## 3. 目标与动机
- 核心驱动力：

## 4. 痛点与挑战
- 资源限制：

## 5. 信息获取渠道
- 知识学习：
- 社交网络：

## 6. 典型场景
- 工作日：
- 周末：

## 7. 标签与分类
- 标签：

## 8. 与产品/服务的关联
- 使用场景：
- 核心需求：

---
保留已有信息，补充新发现的信息。"""
            
            response = self._answer._client.chat.completions.create(
                model=self._answer.llm_model,
                messages=[
                    {"role": "system", "content": "你是专业的用户画像分析师，擅长从记忆数据中提取和整理用户信息。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            
            result = response.choices[0].message.content.strip()
            if "</think>" in result:
                result = result.split("</think>")[1].strip()
            
            if result and result.startswith("#"):
                write_long_term_memory(result)
                logger.info("[记忆调试] 长期记忆已更新")
                return {"code": 200, "message": "长期记忆已更新"}
            else:
                return {"code": 500, "message": "提取结果格式错误"}
                
        except Exception as e:
            logger.warning(f"[记忆调试] 长期记忆提取失败: {e}")
            return {"code": 500, "message": str(e)}

    def _auto_extract_memory(self, question: str, answer: str, history: list):
        """
        自动从对话中提炼重要信息保存到长期记忆
        仅使用LLM智能分析，不再使用硬编码规则
        """
        # 每N轮对话触发一次LLM提炼
        interval = getattr(settings, 'AUTO_MEMORY_INTERVAL', 10)
        # 使用全局对话计数来触发，而不是单个会话的历史长度
        total_messages = self._get_total_message_count()
        if total_messages > 0 and total_messages % interval == 0:
            # 从每日日志读取最近对话进行提炼
            self._llm_extract_memory_from_daily_log()

    def _get_total_message_count(self) -> int:
        """获取今日总对话消息数"""
        try:
            from .memory_service import get_corpus_by_date
            from datetime import datetime
            date = datetime.now().strftime("%Y-%m-%d")
            result = get_corpus_by_date(date)
            if result.get("code") != 200:
                return 0
            entries = result.get("entries", [])
            # 统计用户消息数
            return sum(1 for e in entries if e.get("role") == "USER")
        except Exception:
            return 0

    def _llm_extract_memory_from_daily_log(self):
        """从每日日志读取最近对话进行LLM提炼"""
        try:
            from .memory_service import read_daily_log
            result = read_daily_log()
            if result.get("code") != 200:
                return
            
            log_content = result.get("content", "")
            if not log_content:
                return
            
            # 提取最近N条对话
            self._llm_extract_memory(log_content)
            
        except Exception as e:
            logger.warning(f"从日志提炼记忆失败: {e}")

    def _llm_extract_memory(self, dialog_text: str):
        """
        使用LLM从对话文本中提炼记忆，并按人物画像模板整理
        """
        try:
            
            # 读取现有人物画像
            from .memory_service import read_long_term_memory, write_long_term_memory
            existing = read_long_term_memory()
            existing_profile = existing.get("content", "") if existing.get("code") == 200 else ""
            
            prompt = f"""你是一个专业的用户画像分析师。请根据以下对话内容，更新用户的结构化画像。

## 任务说明
1. 如果已有画像，请在现有基础上补充和修正
2. 如果没有画像，请根据对话创建新的画像
3. 只填写有明确信息的部分，不确定的留空
4. 保持客观，不要推测

## 现有画像
{existing_profile if existing_profile and existing_profile.strip() != "# 长期记忆" else "（暂无）"}

## 新对话记录
{dialog_text}

## 输出格式
请严格按以下模板输出更新后的画像，用 Markdown 格式：

# 用户画像

## 1. 基础信息
- 姓名/代号：
- 性别：
- 年龄：
- 出生地/成长地：
- 教育背景：
- 职业/身份：
- 家庭状况：
- 居住城市：

## 2. 外貌与风格
- 外貌特征：
- 着装风格：
- 配饰习惯：
- 健康/体能：

## 3. 性格与价值观
- MBTI/性格类型：
- 核心价值观：
- 决策模式：
- 风险偏好：
- 情绪稳定性：

## 4. 行为与习惯
- 日常作息：
- 娱乐方式：
- 社交模式：
- 消费习惯：
- 数字设备：

## 5. 目标与动机
- 短期目标（1年内）：
- 中期目标（1-3年）：
- 长期愿景（5年以上）：
- 核心驱动力：

## 6. 痛点与挑战
- 工作/学习压力：
- 人际关系困扰：
- 资源限制：
- 自我怀疑：
- 健康/生活平衡：

## 7. 信息获取渠道
- 知识学习：
- 新闻资讯：
- 社交网络：
- 决策参考：

## 8. 典型场景
- 工作日：
- 周末：
- 假期：

## 9. 语言与表达
- 口头禅/常用语：
- 写作风格：
- 沟通偏好：

## 10. 标签与分类
- 标签：
- 用户细分：

## 12. 与产品/服务的关联
- 使用场景：
- 核心需求：
- 体验期望：
- 流失风险：
---
注意：
- 保留已有画像中的信息，不要丢失
- 新信息补充到对应栏目
- 冲突信息以最新对话为准
- 没有信息的项目保持为空，
- 保持画像"简短可读"，避免信息过载
- 定期更新画像，随着用户洞察深入而演化"""

            response = self._answer._client.chat.completions.create(
                model=self._answer.llm_model,
                messages=[
                    {"role": "system", "content": "你是专业的用户画像分析师，擅长从对话中提取和整理用户信息。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            
            result = response.choices[0].message.content.strip()
            logger.info(f"[记忆调试] LLM返回结果长度: {len(result)}")
            
            # 去除 <think> 标签内容（如果存在）
            if "</think>" in result:
                result = result.split("</think>")[1].strip()
                logger.info(f"[记忆调试] 去除think标签后长度: {len(result)}")
            
            # 保存更新后的画像
            if result and result.startswith("#"):
                write_long_term_memory(result, append=False)
                logger.info("[记忆调试] 用户画像已更新")
            else:
                logger.info(f"[记忆调试] LLM结果不符合保存条件: {result[:100]}")
                        
        except Exception as e:
            logger.warning(f"[记忆调试] LLM记忆提炼失败: {e}")

    def _should_use_memory(self, question: str) -> bool:
        """
        判断是否需要检索记忆
        只有当用户明确询问个人信息时才触发
        """
        import re
        
        # 如果问题是空或太短，不检索
        if not question or len(question.strip()) < 2:
            return False
        
        # 问候语列表 - 不触发记忆检索
        greetings = [
            "你好", "您好", "嗨", "hello", "hi", "hey",
            "早上好", "下午好", "晚上好", "再见", "拜拜",
            "谢谢", "感谢", "不客气", "没关系",
            "在吗", "在吗？", "在不在",
        ]
        
        q = question.strip().lower()
        
        # 纯问候语不触发
        for g in greetings:
            if q == g.lower() or q.startswith(g.lower()):
                return False
        
        # 询问AI自身的问题不触发
        ai_self_patterns = [
            r"你.*?(是|叫|名字|谁|什么)",
            r"介绍.*?(你|自己)",
            r"你.*?能.*?做",
            r"你.*?会.*?什么",
            r"帮助|帮忙",
        ]
        for pattern in ai_self_patterns:
            if re.search(pattern, q):
                return False
        
        # 简单问题（长度<10且无个人信息关键词）不触发
        if len(q) < 10:
            # 检查是否包含个人信息关键词
            personal_keywords = [
                "我", "我的", "名字", "年龄", "职业", "工作",
                "喜欢", "爱好", "兴趣", "来自", "哪里",
                "小明", "小红", "小张",
            ]
            has_personal = any(kw in q for kw in personal_keywords)
            if not has_personal:
                return False
        
        return True

    def _get_user_preferences(self) -> str:
        """
        从长期记忆中提取结构化的用户画像
        返回总结后的画像信息，用于注入系统提示
        """
        try:
            from .memory_service import read_long_term_memory
            result = read_long_term_memory()
            if result.get("code") != 200:
                return ""
            
            content = result.get("content", "")
            if not content or content.strip() in ("# 长期记忆", "# 用户画像"):
                return ""
            
            # 提取已填写的信息（过滤掉空项）
            filled_info = []
            current_section = ""
            
            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                
                # 记录当前章节
                if line.startswith("## "):
                    current_section = line.replace("## ", "").strip()
                    continue
                
                # 提取有内容的条目
                if line.startswith("-") and ":" in line:
                    parts = line[1:].split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # 只保留有值的项
                        if value and value not in ("无", "暂无", "不确定", "未提及"):
                            filled_info.append(f"{current_section} - {key}: {value}")
            
            if not filled_info:
                return ""
            
            return "\n".join(filled_info[:20])  # 最多20条
            
        except Exception as e:
            logger.warning(f"获取用户画像失败: {e}")
            return ""

    def _build_context(self, chunks: List[dict]) -> str:
        if not chunks:
            return ""
        parts = []
        for i, c in enumerate(chunks):
            # 优先使用原始chunk内容，如果混合检索丢失了content，从chunk_meta找回
            content = c.get('content', '')
            if not content and hasattr(self, '_vector_store'):
                # 尝试从vector_store获取完整内容
                try:
                    doc_id = c.get('doc_id')
                    if doc_id:
                        for chunk in self._vector_store._chunk_meta:
                            if chunk.get('doc_id') == doc_id and chunk.get('content'):
                                content = chunk['content']
                                break
                except:
                    pass
            parts.append(f"[{i+1}] {c['metadata'].get('filename', c['doc_id'])}: {content[:500]}")
        return "\n\n".join(parts)

    def _build_meta_context(self, docs: List[dict], stats: dict) -> str:
        if not docs:
            return "暂无文档"
        lines = [f"共{len(docs)}个文档，{stats.get('total_chunks', 0)}个块"]
        for i, d in enumerate(docs, 1):
            lines.append(f"{i}. {d.get('filename', d['doc_id'])} ({d.get('chunk_count', 0)}块)")
        return "\n".join(lines)


# ========== 全局单例 ==========
rag_service = RAGService()


# ========== 会话历史管理（持久化）==============
import json
from pathlib import Path

_HISTORY_FILE = Path(__file__).resolve().parents[2] / "backend" / "conversations.json"
_HISTORY_STORE: dict = {}
_HISTORY_LOCK = __import__("threading").Lock()

# 会话标题存储
_TITLE_FILE = Path(__file__).resolve().parents[2] / "backend" / "session_titles.json"
_SESSION_TITLES: dict = {}


def _load_titles_from_disk():
    """从磁盘加载会话标题"""
    global _SESSION_TITLES
    if _TITLE_FILE.exists():
        try:
            data = json.loads(_TITLE_FILE.read_text(encoding="utf-8"))
            _SESSION_TITLES = data
        except Exception as e:
            print(f"加载会话标题失败: {e}")

def _save_titles_to_disk():
    """保存会话标题到磁盘"""
    try:
        _TITLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TITLE_FILE.write_text(json.dumps(_SESSION_TITLES, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"保存会话标题失败: {e}")

def _get_session_title(session_id: str) -> str:
    """获取会话标题，如果没有则返回ID的前8位"""
    return _SESSION_TITLES.get(session_id, session_id[:8])

def _set_session_title(session_id: str, query: str):
    """设置会话标题（只设置一次，取前20个字符）"""
    if session_id not in _SESSION_TITLES:
        # 取提问的前20个字符作为标题
        title = query.strip()[:30] if query.strip() else session_id[:8]
        _SESSION_TITLES[session_id] = title
        _save_titles_to_disk()


def _load_history_from_disk():
    """从磁盘加载会话历史"""
    if _HISTORY_FILE.exists():
        try:
            data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            _HISTORY_STORE.update(data)
            print(f"已加载 {len(_HISTORY_STORE)} 个会话历史")
        except Exception as e:
            print(f"加载会话历史失败: {e}")

def _save_history_to_disk():
    """保存会话历史到磁盘"""
    try:
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_FILE.write_text(json.dumps(_HISTORY_STORE, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"保存会话历史失败: {e}")

# 启动时加载
_load_history_from_disk()
_load_titles_from_disk()


def get_all_sessions() -> list:
    """获取所有会话ID列表"""
    return list(_HISTORY_STORE.keys())


def get_all_sessions_with_titles() -> list:
    """获取所有会话（带标题）"""
    sessions = []
    for sid in _HISTORY_STORE.keys():
        title = _SESSION_TITLES.get(sid, sid[:8])
        sessions.append({"id": sid, "title": title})
    return sessions


def get_conversation_history(session_id: str, max_turns: int = 5) -> list:
    """获取会话历史"""
    with _HISTORY_LOCK:
        history = _HISTORY_STORE.get(session_id, [])
    return history[-max_turns*2:]


def add_to_history(session_id: str, query: str, answer: str):
    """添加到会话历史"""
    with _HISTORY_LOCK:
        if session_id not in _HISTORY_STORE:
            _HISTORY_STORE[session_id] = []
        _HISTORY_STORE[session_id].extend([{"role": "user", "content": query}, {"role": "assistant", "content": answer}])
        if len(_HISTORY_STORE[session_id]) > 20:
            _HISTORY_STORE[session_id] = _HISTORY_STORE[session_id][-20:]
        _save_history_to_disk()  # 每次保存
    
    # 设置会话标题（如果是新会话）
    _set_session_title(session_id, query)


def delete_session(session_id: str) -> bool:
    """删除指定会话"""
    with _HISTORY_LOCK:
        if session_id in _HISTORY_STORE:
            del _HISTORY_STORE[session_id]
            _save_history_to_disk()
            # 同时删除标题
            if session_id in _SESSION_TITLES:
                del _SESSION_TITLES[session_id]
                _save_titles_to_disk()
            return True
    return False


def clear_all_sessions() -> bool:
    """清空所有会话"""
    with _HISTORY_LOCK:
        _HISTORY_STORE.clear()
        _save_history_to_disk()
        _SESSION_TITLES.clear()
        _save_titles_to_disk()
    return True