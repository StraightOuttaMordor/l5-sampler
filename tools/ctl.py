#!/usr/bin/env python3
"""Send one JSON command to the running app's test socket. Usage: ctl.py '{"cmd":"state"}'"""
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('/tmp/l5s.sock')
s.sendall((sys.argv[1] + '\n').encode())
buf = b''
while not buf.endswith(b'\n'):
    d = s.recv(65536)
    if not d:
        break
    buf += d
print(buf.decode().strip())
