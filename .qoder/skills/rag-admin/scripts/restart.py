#!/usr/bin/env python3
"""
重启 RAG 前后端服务
Usage: python scripts/restart.py [backend|frontend|all]
"""
import os
import signal
import subprocess
import sys
import time

PROJ_ROOT = "/home/10359121/10359121/pro2"
VENV_BIN = f"{PROJ_ROOT}/.venv/bin"
BACKEND_DIR = f"{PROJ_ROOT}/backend"
FRONTEND_DIR = f"{PROJ_ROOT}/frontend"


def kill_port(port: int):
    """关闭指定端口的进程"""
    try:
        result = subprocess.run(
            ["lsof", "-t", f"-i:{port}"],
            capture_output=True, text=True,
        )
        for pid in result.stdout.strip().split("\n"):
            if pid:
                os.kill(int(pid), signal.SIGTERM)
                print(f"  已关闭 PID {pid} (端口 {port})")
    except Exception:
        pass


def start_backend():
    """启动后端"""
    print("启动后端...")
    os.chdir(BACKEND_DIR)
    subprocess.Popen(
        [f"{VENV_BIN}/python", "run.py"],
        env={**os.environ, "VIRTUAL_ENV": PROJ_ROOT + "/.venv"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("  后端启动中 (http://localhost:8000)")


def start_frontend():
    """启动前端"""
    print("启动前端...")
    os.chdir(FRONTEND_DIR)
    subprocess.Popen(
        [f"{VENV_BIN}/streamlit", "run", "app.py", "--server.port", "8501"],
        env={**os.environ, "VIRTUAL_ENV": PROJ_ROOT + "/.venv"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("  前端启动中 (http://localhost:8501)")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if target in ("backend", "all"):
        kill_port(8000)
        time.sleep(1)
        start_backend()

    if target in ("frontend", "all"):
        kill_port(8501)
        time.sleep(1)
        start_frontend()

    print("\n服务已启动完成")


if __name__ == "__main__":
    main()
