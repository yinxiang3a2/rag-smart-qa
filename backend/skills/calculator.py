"""
计算器技能
提供基础数学运算
"""

SKILL_NAME = "计算器"
SKILL_DESCRIPTION = "执行基础数学运算（加减乘除）"
SKILL_TRIGGER = ["计算", "加", "减", "乘", "除", "等于", "多少"]

def run(expression: str = "1+1"):
    """
    执行数学计算
    
    参数:
        expression: 数学表达式，如 "1+1", "10*5"
    
    返回:
        str: 计算结果
    """
    try:
        # 安全计算：只允许数字和运算符
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "表达式包含非法字符，只允许数字和+-*/.()"
        
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"
