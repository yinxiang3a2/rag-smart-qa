#!/usr/bin/env python3
"""极简 HTTP CONNECT 代理隧道 - 用于 SSH ProxyCommand"""
import socket, sys, os, select

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect(('proxy.zte.com.cn', 80))

host, port = sys.argv[1], sys.argv[2]
req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n"
sock.sendall(req.encode())

resp = b""
while b"\r\n\r\n" not in resp:
    chunk = sock.recv(4096)
    if not chunk:
        break
    resp += chunk

if b"200" not in resp:
    os.write(2, f"Proxy error: {resp.decode(errors='ignore')}\n".encode())
    sys.exit(1)

# 双向转发 - 使用os.read/write避免Python缓冲
try:
    while True:
        r, _, _ = select.select([0, sock.fileno()], [], [])
        if 0 in r:
            data = os.read(0, 8192)
            if not data:
                break
            sock.sendall(data)
        if sock.fileno() in r:
            data = sock.recv(8192)
            if not data:
                break
            os.write(1, data)
except Exception:
    pass
finally:
    sock.close()
