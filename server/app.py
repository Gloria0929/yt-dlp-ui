"""FastAPI HTTP/SSE service backed by isolated native yt_dlp workers."""
import asyncio
import json
import multiprocessing
import os
import queue
import shutil
import signal
import time
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from yt_dlp.version import __version__ as yt_dlp_version

from server.downloader import media_worker
from server.models import ROOT, MediaRequest
from server.task_files import (
    TASKS,
    TASK_TTL_SECONDS,
    cleanup_expired_tasks,
    cleanup_orphan_directories,
    create_task_directory,
    get_task_file,
    register_task_files,
    release_task_file,
    remove_task,
)

CONTEXT = multiprocessing.get_context("spawn")
ACTIVE = set()
MAX_WORKERS = max(1, int(os.environ.get("YTDLP_MAX_WORKERS", "4")))


def stop_worker(process):
    if process.pid:
        process.join(timeout=0.25)
        if process.is_alive():
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    process.terminate()
            else:
                process.terminate()
            process.join(timeout=0.5)
        if process.is_alive():
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    process.kill()
            else:
                process.kill()
            process.join(timeout=0.3)
    ACTIVE.discard(process)
    process.close()


async def cleanup_loop():
    interval = min(300, max(30, TASK_TTL_SECONDS // 2))
    while True:
        await asyncio.sleep(interval)
        await asyncio.to_thread(cleanup_expired_tasks)
        await asyncio.to_thread(cleanup_orphan_directories)


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(cleanup_orphan_directories)
    cleanup_task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        for process in list(ACTIVE):
            await asyncio.to_thread(stop_worker, process)
        for task_id in list(TASKS):
            await asyncio.to_thread(remove_task, task_id)


app = FastAPI(title="yt-dlp 下载工作台", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    messages = [
        f"{'.'.join(str(part) for part in item['loc'][1:])}: {item['msg']}"
        for item in error.errors()
    ]
    return JSONResponse(status_code=422, content={"error": "；".join(messages)})


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "backend": "FastAPI",
        "engine": "yt_dlp",
        "version": yt_dlp_version,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "storage": "browser",
        "taskTtlSeconds": TASK_TTL_SECONDS,
    }


@app.get("/api/version")
async def version():
    return {"version": yt_dlp_version}


async def worker_events(action, payload, request, settings_data=None):
    events = CONTEXT.Queue(maxsize=256)
    process = CONTEXT.Process(
        target=media_worker,
        args=(
            action,
            payload.url,
            settings_data or payload.settings.model_dump(),
            events,
        ),
    )
    process.start()
    ACTIVE.add(process)
    start = last_ping = time.monotonic()
    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                event = events.get_nowait()
            except queue.Empty:
                if not process.is_alive():
                    try:
                        event = await asyncio.to_thread(events.get, True, 0.2)
                    except queue.Empty:
                        yield {"type": "error", "error": "下载进程意外结束，请重新尝试"}
                        return
                else:
                    if action == "info" and time.monotonic() - start > 120:
                        yield {
                            "type": "error",
                            "error": "解析超过 120 秒，请检查网络、代理或登录状态",
                        }
                        return
                    if time.monotonic() - last_ping > 10:
                        yield {"type": "heartbeat"}
                        last_ping = time.monotonic()
                    await asyncio.sleep(0.05)
                    continue
            yield event
            if event["type"] in ("done", "error", "info"):
                return
    finally:
        await asyncio.to_thread(stop_worker, process)
        events.close()
        events.join_thread()


def busy_response():
    if len(ACTIVE) >= MAX_WORKERS:
        return JSONResponse(
            status_code=429,
            content={"error": "当前任务较多，请等待已有任务完成后重试"},
        )
    return None


@app.post("/api/extract-info")
async def extract_info(payload: MediaRequest, request: Request):
    if busy := busy_response():
        return busy
    async for event in worker_events("info", payload, request):
        if event["type"] == "info":
            return {"ok": True, "info": event["info"]}
        if event["type"] == "error":
            return JSONResponse(status_code=502, content={"error": event["error"]})
    return JSONResponse(status_code=499, content={"error": "解析已取消"})


@app.post("/api/download")
async def download(payload: MediaRequest, request: Request):
    if busy := busy_response():
        return busy
    settings = payload.settings
    if (
        settings.mode == "audio"
        or settings.container
        or settings.embedSubs
        or settings.embedMetadata
        or settings.embedThumbnail
    ) and not shutil.which("ffmpeg"):
        return JSONResponse(
            status_code=422,
            content={"error": "当前选项需要 ffmpeg，请安装 ffmpeg 后重新下载"},
        )

    task_id, task_dir = create_task_directory()
    settings_data = settings.model_dump()
    # Never trust a browser-supplied server path. Every request gets an isolated
    # short-lived directory and the result is transferred back to that browser.
    settings_data["outputDir"] = str(task_dir)

    async def stream():
        ready = False
        try:
            async for event in worker_events(
                "download", payload, request, settings_data=settings_data
            ):
                if event["type"] == "done":
                    try:
                        event["files"] = await asyncio.to_thread(
                            register_task_files, task_id, task_dir
                        )
                        ready = True
                    except Exception as error:
                        event = {"type": "error", "error": str(error)}
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            if not ready:
                await asyncio.to_thread(remove_task, task_id, task_dir)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/files/{task_id}/{file_id}")
async def transfer_file(task_id: str, file_id: str):
    path = get_task_file(task_id, file_id)
    if path is None:
        return JSONResponse(
            status_code=404,
            content={"error": "文件已过期、已下载或不存在，请重新创建任务"},
        )
    return FileResponse(
        path,
        filename=path.name,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(release_task_file, task_id, file_id),
    )


@app.delete("/api/files/{task_id}/{file_id}")
async def discard_file(task_id: str, file_id: str):
    if get_task_file(task_id, file_id) is None:
        return JSONResponse(status_code=404, content={"error": "文件不存在或已过期"})
    await asyncio.to_thread(release_task_file, task_id, file_id)
    return {"ok": True}


if (ROOT / "client" / "dist").is_dir():
    app.mount(
        "/",
        StaticFiles(directory=ROOT / "client" / "dist", html=True),
        name="frontend",
    )
