#!/usr/bin/env python3
"""
测试 RAG 检索效果
Usage: python scripts/test_search.py "登录功能测试"
"""
import os
import sys
import requests

os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)

BACKEND_URL = "http://localhost:8000"


def main(query: str = None):
    if not query:
        if len(sys.argv) < 2:
            print("用法: python test_search.py \"你的测试问题\"")
            print("示例: python test_search.py \"登录功能测试\"")
            sys.exit(1)
        query = sys.argv[1]

    try:
        r = requests.post(
            f"{BACKEND_URL}/api/v1/chat",
            json={"query": query, "top_k": 5},
            timeout=30,
        )
        data = r.json()
        sources = data.get("sources", [])
        answer = data.get("answer", "")

        print(f"=== 检索测试: \"{query}\" ===")
        print(f"检索到 {len(sources)} 个相关文档\n")

        for i, s in enumerate(sources, 1):
            print(f"[{i}] {s.get('doc_name', 'unknown')}")
            print(f"    相关性: {s.get('score', 0):.2%}")
            print(f"    内容: {s.get('content', '')[:100]}...")
            print()

        print("--- LLM 回答 ---")
        print(answer[:300] + ("..." if len(answer) > 300 else ""))

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
