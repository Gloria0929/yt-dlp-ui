"""Short-lived download artifacts exposed through unguessable task URLs."""
import os
import secrets
import shutil
import time
from pathlib import Path


IGNORED_SUFFIXES = {".part", ".ytdl", ".temp"}

TEMP_ROOT = Path(os.environ.get("YTDLP_TEMP_DIR", "/tmp/yt-dlp-ui")).resolve()
TASK_TTL_SECONDS = max(60, int(os.environ.get("YTDLP_TASK_TTL", "3600")))
TASKS = {}


def create_task_directory():
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    while True:
        task_id = secrets.token_urlsafe(24)
        task_dir = TEMP_ROOT / task_id
        try:
            task_dir.mkdir(mode=0o700)
            return task_id, task_dir
        except FileExistsError:
            continue


def _downloadable_files(task_dir):
    return [
        path
        for path in sorted(task_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() not in IGNORED_SUFFIXES
    ]


def register_task_files(task_id, task_dir):
    files = {}
    public_files = []
    for path in _downloadable_files(task_dir):
        file_id = secrets.token_urlsafe(16)
        relative_path = path.relative_to(task_dir).as_posix()
        files[file_id] = path
        public_files.append({
            "id": file_id,
            "name": path.name,
            "relativePath": relative_path,
            "size": path.stat().st_size,
            "downloadUrl": f"/api/files/{task_id}/{file_id}",
        })
    if not public_files:
        raise RuntimeError("下载完成，但没有找到可发送到浏览器的文件")
    TASKS[task_id] = {
        "directory": task_dir,
        "created": time.time(),
        "files": files,
    }
    return public_files


def snapshot_directory(directory):
    """记录目录当前状态，用于识别某个任务新写入的文件。"""
    snapshot = {}
    root = Path(directory)
    if not root.is_dir():
        return snapshot
    for path in root.rglob("*"):
        try:
            if path.is_file():
                stat = path.stat()
                snapshot[str(path)] = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            continue
    return snapshot


def register_written_files(directory, before):
    """桌面版直写模式：报告本次新写入或改动的文件，不需要再传回浏览器。"""
    root = Path(directory)
    written = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if before.get(str(path)) == (stat.st_mtime_ns, stat.st_size):
            continue
        written.append({
            "id": secrets.token_urlsafe(16),
            "name": path.name,
            "relativePath": path.relative_to(root).as_posix(),
            "absolutePath": str(path),
            "size": stat.st_size,
            "saved": True,
        })
    return written


def get_task_file(task_id, file_id):
    task = TASKS.get(task_id)
    if not task:
        return None
    path = task["files"].get(file_id)
    if not path or not path.is_file():
        return None
    return path


def remove_task(task_id, directory=None):
    task = TASKS.pop(task_id, None)
    target = task["directory"] if task else directory
    if target:
        shutil.rmtree(target, ignore_errors=True)


def release_task_file(task_id, file_id):
    task = TASKS.get(task_id)
    if not task:
        return
    path = task["files"].pop(file_id, None)
    if path:
        path.unlink(missing_ok=True)
    if not task["files"]:
        remove_task(task_id)


def cleanup_expired_tasks(now=None):
    cutoff = (time.time() if now is None else now) - TASK_TTL_SECONDS
    expired = [
        task_id
        for task_id, task in list(TASKS.items())
        if task["created"] < cutoff
    ]
    for task_id in expired:
        remove_task(task_id)
    return len(expired)


def cleanup_orphan_directories():
    if not TEMP_ROOT.exists():
        return
    cutoff = time.time() - TASK_TTL_SECONDS
    for path in TEMP_ROOT.iterdir():
        if path.is_dir() and path.stat().st_mtime < cutoff:
            shutil.rmtree(path, ignore_errors=True)
