"""
技能管理系统
支持动态加载用户自定义技能
"""
import importlib.util
import inspect
import logging
import os
from pathlib import Path
from typing import Dict, List, Callable, Any, Optional

from ..config import settings

logger = logging.getLogger(__name__)

# 技能目录
SKILLS_DIR = settings.BASE_DIR / "skills"
SKILLS_DIR.mkdir(exist_ok=True)

# 已注册的技能
_REGISTERED_SKILLS: Dict[str, dict] = {}


class Skill:
    """技能对象"""
    def __init__(self, name: str, description: str, trigger_words: List[str], 
                 func: Callable, params: List[dict], file_path: str):
        self.name = name
        self.description = description
        self.trigger_words = trigger_words
        self.func = func
        self.params = params  # 参数定义 [{"name": "city", "type": "str", "required": True}]
        self.file_path = file_path
    
    def execute(self, **kwargs) -> dict:
        """执行技能"""
        try:
            result = self.func(**kwargs)
            return {"code": 200, "result": result}
        except Exception as e:
            logger.error(f"技能 {self.name} 执行失败: {e}")
            return {"code": 500, "error": str(e)}
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "trigger_words": self.trigger_words,
            "params": self.params,
            "file_path": self.file_path,
        }


def _scan_skills() -> List[Path]:
    """扫描技能目录下的所有Python文件"""
    skills = []
    if SKILLS_DIR.exists():
        for f in SKILLS_DIR.glob("*.py"):
            if not f.name.startswith("_"):
                skills.append(f)
    return skills


def _load_skill_file(file_path: Path) -> Optional[Skill]:
    """加载单个技能文件"""
    try:
        # 动态导入模块
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 读取元数据
        name = getattr(module, "SKILL_NAME", file_path.stem)
        description = getattr(module, "SKILL_DESCRIPTION", "")
        trigger_words = getattr(module, "SKILL_TRIGGER", [])
        
        # 查找执行函数
        func = getattr(module, "run", None)
        if func is None:
            logger.warning(f"技能文件 {file_path} 没有 run 函数")
            return None
        
        # 解析参数
        sig = inspect.signature(func)
        params = []
        for param_name, param in sig.parameters.items():
            param_info = {
                "name": param_name,
                "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "str",
                "required": param.default == inspect.Parameter.empty,
                "default": param.default if param.default != inspect.Parameter.empty else None,
            }
            params.append(param_info)
        
        return Skill(
            name=name,
            description=description,
            trigger_words=trigger_words,
            func=func,
            params=params,
            file_path=str(file_path),
        )
    except Exception as e:
        logger.error(f"加载技能文件 {file_path} 失败: {e}")
        return None


def reload_skills() -> dict:
    """重新加载所有技能"""
    global _REGISTERED_SKILLS
    _REGISTERED_SKILLS.clear()
    
    loaded = 0
    failed = 0
    
    for file_path in _scan_skills():
        skill = _load_skill_file(file_path)
        if skill:
            _REGISTERED_SKILLS[skill.name] = skill
            loaded += 1
        else:
            failed += 1
    
    return {
        "code": 200,
        "message": f"已加载 {loaded} 个技能，失败 {failed} 个",
        "skills": [s.to_dict() for s in _REGISTERED_SKILLS.values()],
    }


def get_all_skills() -> List[dict]:
    """获取所有已注册技能"""
    return [s.to_dict() for s in _REGISTERED_SKILLS.values()]


def get_skill(name: str) -> Optional[Skill]:
    """获取指定技能"""
    return _REGISTERED_SKILLS.get(name)


def match_skill(question: str) -> Optional[Skill]:
    """
    根据用户问题匹配技能
    返回最匹配的技能，如果没有则返回None
    """
    question_lower = question.lower()
    
    best_match = None
    best_score = 0
    
    for skill in _REGISTERED_SKILLS.values():
        score = 0
        for trigger in skill.trigger_words:
            if trigger.lower() in question_lower:
                score += len(trigger)  # 越长匹配越精准
        
        if score > best_score:
            best_score = score
            best_match = skill
    
    return best_match


def execute_skill(name: str, **kwargs) -> dict:
    """执行指定技能"""
    skill = get_skill(name)
    if skill is None:
        return {"code": 404, "error": f"技能 {name} 不存在"}
    
    return skill.execute(**kwargs)


def delete_skill_file(name: str) -> dict:
    """删除技能文件"""
    skill = get_skill(name)
    if skill is None:
        return {"code": 404, "error": "技能不存在"}
    
    try:
        file_path = Path(skill.file_path)
        if file_path.exists():
            file_path.unlink()
        
        # 从注册表中移除
        if name in _REGISTERED_SKILLS:
            del _REGISTERED_SKILLS[name]
        
        return {"code": 200, "message": f"技能 {name} 已删除"}
    except Exception as e:
        return {"code": 500, "error": str(e)}


def create_skill_file(name: str, code: str) -> dict:
    """创建新的技能文件"""
    try:
        # 安全检查：文件名只能包含字母数字下划线
        safe_name = "".join(c for c in name if c.isalnum() or c == "_")
        if not safe_name:
            return {"code": 400, "error": "技能名称无效"}
        
        file_path = SKILLS_DIR / f"{safe_name}.py"
        file_path.write_text(code, encoding="utf-8")
        
        # 尝试加载新技能
        skill = _load_skill_file(file_path)
        if skill:
            _REGISTERED_SKILLS[skill.name] = skill
            return {"code": 200, "message": f"技能 {skill.name} 创建成功", "skill": skill.to_dict()}
        else:
            # 加载失败，删除文件
            file_path.unlink()
            return {"code": 400, "error": "技能代码格式错误，请检查是否包含 run 函数和必要的元数据"}
    except Exception as e:
        return {"code": 500, "error": str(e)}


# 启动时自动加载
reload_skills()
