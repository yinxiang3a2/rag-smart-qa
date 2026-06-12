"""
技能管理API
提供技能的CRUD和执行接口
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List, Optional

from app.services.skill_manager import (
    reload_skills,
    get_all_skills,
    get_skill,
    match_skill,
    execute_skill,
    delete_skill_file,
    create_skill_file,
    SKILLS_DIR,
)

router = APIRouter(prefix="/api/v1/skills", tags=["技能管理"])


# ========== 请求模型 ==========

class CreateSkillRequest(BaseModel):
    name: str
    code: str


class ExecuteSkillRequest(BaseModel):
    name: str
    params: Dict[str, str] = {}


class MatchSkillRequest(BaseModel):
    question: str


# ========== 技能管理API ==========

@router.get("/")
async def api_list_skills():
    """列出所有已注册技能"""
    return {"code": 200, "skills": get_all_skills()}


@router.post("/reload")
async def api_reload_skills():
    """重新加载所有技能"""
    return reload_skills()


@router.post("/")
async def api_create_skill(req: CreateSkillRequest):
    """创建新技能"""
    return create_skill_file(req.name, req.code)


@router.get("/{name}")
async def api_get_skill(name: str):
    """获取技能详情"""
    skill = get_skill(name)
    if skill is None:
        return {"code": 404, "error": "技能不存在"}
    return {"code": 200, "skill": skill.to_dict()}


@router.delete("/{name}")
async def api_delete_skill(name: str):
    """删除技能"""
    return delete_skill_file(name)


# ========== 技能执行API ==========

@router.post("/execute")
async def api_execute_skill(req: ExecuteSkillRequest):
    """执行指定技能"""
    return execute_skill(req.name, **req.params)


@router.post("/match")
async def api_match_skill(req: MatchSkillRequest):
    """根据问题匹配技能"""
    skill = match_skill(req.question)
    if skill is None:
        return {"code": 200, "matched": False, "message": "没有匹配的技能"}
    return {
        "code": 200,
        "matched": True,
        "skill": skill.to_dict(),
    }


# ========== 技能模板API ==========

@router.get("/template/default")
async def api_skill_template():
    """获取默认技能模板"""
    template = '''"""
{skill_name} 技能
{description}
"""

# 技能元数据
SKILL_NAME = "{skill_name}"
SKILL_DESCRIPTION = "{description}"
SKILL_TRIGGER = {trigger_words}

# 导入需要的库
# import requests
# import json

def run({params}):
    """
    技能执行函数
    
    参数:
        {param_docs}
    
    返回:
        str: 执行结果
    """
    # 在这里写你的逻辑
    result = f"收到参数: {locals()}"
    
    return result
'''
    return {
        "code": 200,
        "template": template,
        "example": '''"""
天气查询技能示例
查询指定城市的天气
"""

SKILL_NAME = "天气查询"
SKILL_DESCRIPTION = "查询指定城市的天气信息"
SKILL_TRIGGER = ["天气", "温度", "下雨", "晴天"]

def run(city: str = "北京"):
    """
    查询城市天气
    
    参数:
        city: 城市名称
    
    返回:
        str: 天气信息
    """
    # 这里可以调用真实天气API
    return f"{city}今天天气晴朗，气温25°C"
''',
    }
