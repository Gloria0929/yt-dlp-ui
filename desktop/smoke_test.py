"""End-to-end smoke test for the packaged desktop backend.

Starts the frozen backend, runs a real download through the SSE API, transfers the
result exactly like desktop/main.cjs does, and verifies the file is removed from the
temporary task directory afterwards.
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BINARY = ROOT / "desktop" / "build" / "frame-get-api" / "frame-get-api"
FFMPEG_DIR = ROOT / "desktop" / "build" / "ffmpeg"
SAMPLE = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
TOKEN = "e2e-token"
OUT = Path("/tmp/fg-e2e-out")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def call(url, method="GET", payload=None, raw=False):
    request = urllib.request.Request(url, method=method)
    request.add_header("X-Desktop-Token", TOKEN)
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, body, timeout=180) as response:
        data = response.read()
        return data if raw else json.loads(data)


def main() -> int:
    if not BINARY.exists():
        print("SKIP: 未找到冻结后端，先运行 npm run desktop:backend")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    port = free_port()
    env = {
        **os.environ,
        "PORT": str(port),
        "YTDLP_DESKTOP_TOKEN": TOKEN,
        "YTDLP_TEMP_DIR": "/tmp/fg-e2e-tasks",
        "PATH": str(FFMPEG_DIR) + os.pathsep + os.environ["PATH"],
    }
    child = subprocess.Popen([str(BINARY)], env=env, cwd=str(BINARY.parent),
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                health = call(base + "/api/health")
                if health.get("ok"):
                    break
            except Exception:
                time.sleep(0.25)
        else:
            print("FAIL: 后端未就绪", child.stderr.read(2000).decode())
            return 1
        print("health:", health["engine"], health["version"], "ffmpeg=", health["ffmpeg"])

        payload = {"url": SAMPLE, "settings": {"mode": "video", "quality": "best", "container": "mp4"}}
        request = urllib.request.Request(base + "/api/download", method="POST",
                                         data=json.dumps(payload).encode())
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Desktop-Token", TOKEN)
        events, files = [], []
        with urllib.request.urlopen(request, timeout=180) as stream:
            for line in stream:
                text = line.decode().strip()
                if not text.startswith("data:"):
                    continue
                event = json.loads(text[5:])
                events.append(event["type"])
                if event["type"] == "error":
                    print("FAIL: 下载事件报错", event["error"])
                    return 1
                if event["type"] == "done":
                    files = event.get("files", [])
        print("events:", ",".join(sorted(set(events))), "files:", len(files))
        if not files:
            print("FAIL: 下载完成但没有返回文件")
            return 1

        for item in files:
            data = call(base + item["downloadUrl"], raw=True)
            target = OUT / item["relativePath"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            print("saved:", item["relativePath"], len(data), "bytes")
            if not data.startswith(b"\x00\x00\x00") and b"ftyp" not in data[:32]:
                print("FAIL: 文件头不是 MP4")
                return 1
            if len(data) < 100_000:
                print("FAIL: 文件过小", len(data))
                return 1
            try:
                call(base + item["downloadUrl"])
                print("FAIL: 文件传输后仍可再次下载，一次性释放失效")
                return 1
            except urllib.error.HTTPError as error:
                print("one-shot release ok, 再次访问 ->", error.code)
        print("E2E PASS")
        return 0
    finally:
        child.send_signal(signal.SIGTERM)
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
        print("backend exit code:", child.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
