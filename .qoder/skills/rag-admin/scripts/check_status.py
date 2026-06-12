#!/usr/bin/env python3
"""
查看 RAG 系统状态
Usage: python scripts/check_status.py
"""
import os
import sys
import requests

os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)

BACKEND_URL = "http://localhost:8000"


def main():
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/chat/health", timeout=5)
        data = r.json()
        stats = data.get("stats", {})
        print("=== RAG 系统状态 ===")
        print(f"  服务状态: {data.get('status', 'unknown')}")
        print(f"  向量库类型: {stats.get('store_type', 'unknown')}")
        print(f"  已索引文档数: {stats.get('total_documents', 0)}")
        print(f"  文本块总数: {stats.get('total_chunks', 0)}")
        if stats.get('index_path'):
            print(f"  索引路径: {stats['index_path']}")
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务，请确认后端已启动（python backend/run.py）")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
