#!/usr/bin/env python3
"""
Python 文件语法检查（检查常见规范问题）
Usage: python scripts/check_syntax.py backend/app/services/embedding_service.py
"""
import ast
import sys


def check_file(filepath: str) -> list[str]:
    """检查文件中的常见规范问题"""
    errors = []

    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [f"语法错误: {e}"]

    # 检查1: 禁止 bare except
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            errors.append(f"第 {node.lineno} 行: 禁止使用 bare except，应使用 except Exception")

    # 检查2: 检查 set_page_config 重复调用
    lines = source.split("\n")
    page_config_lines = [i + 1 for i, l in enumerate(lines) if "set_page_config" in l]
    if len(page_config_lines) > 1:
        errors.append(f"set_page_config 出现 {len(page_config_lines)} 次（第 {page_config_lines} 行），Streamlit 只能调用一次")

    # 检查3: 检查是否清除 SOCKS 代理（外部 API 调用文件）
    if any(k in filepath for k in ["embedding", "llm", "api", "service"]):
        has_clear = "all_proxy" in source or "ALL_PROXY" in source
        has_requests = "requests" in source or "httpx" in source or "openai" in source
        if has_requests and not has_clear:
            errors.append("外部 API 调用文件未清除 SOCKS 代理（添加: os.environ.pop('all_proxy', None)）")

    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python check_syntax.py <文件路径>")
        sys.exit(1)

    filepath = sys.argv[1]
    errors = check_file(filepath)

    if errors:
        print(f"检查 {filepath}:")
        for err in errors:
            print(f"  ⚠️  {err}")
        sys.exit(1)
    else:
        print(f"✅ {filepath} 未发现规范问题")


if __name__ == "__main__":
    main()
