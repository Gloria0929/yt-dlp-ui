"""桌面版直写模式：目录快照、新文件识别，以及仅桌面可用的守卫。"""
import os
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.app import app
from server.task_files import register_written_files, snapshot_directory


def test_snapshot_and_register_written_files(tmp_path):
    existing = tmp_path / "old.mp4"
    existing.write_bytes(b"old")
    before = snapshot_directory(tmp_path)
    assert list(before) == [str(existing)]

    (tmp_path / "new.mp4").write_bytes(b"new-file")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "child.mp3").write_bytes(b"child")
    (nested / "child.mp4.part").write_bytes(b"partial")

    written = register_written_files(tmp_path, before)
    assert [item["relativePath"] for item in written] == ["new.mp4", "sub/child.mp3"]
    assert all(item["saved"] is True for item in written)
    assert all(Path(item["absolutePath"]).is_absolute() for item in written)


def test_unchanged_files_are_not_reported(tmp_path):
    target = tmp_path / "same.mp4"
    target.write_bytes(b"payload")
    before = snapshot_directory(tmp_path)
    assert register_written_files(tmp_path, before) == []


def test_direct_write_requires_desktop_shell(tmp_path):
    payload = {
        "url": "https://example.com/video",
        "settings": {"directWrite": True, "outputDir": str(tmp_path)},
    }
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("YTDLP_DESKTOP_TOKEN", None)
        with TestClient(app) as client:
            response = client.post("/api/download", json=payload)
    assert response.status_code == 400
    assert response.json()["error"] == "直接写入本机目录仅在桌面版可用"


def test_direct_write_requires_absolute_path(tmp_path):
    payload = {
        "url": "https://example.com/video",
        "settings": {"directWrite": True, "outputDir": "relative/folder"},
    }
    with patch.dict(os.environ, {"YTDLP_DESKTOP_TOKEN": "test-token"}):
        with TestClient(app) as client:
            response = client.post(
                "/api/download", json=payload, headers={"X-Desktop-Token": "test-token"}
            )
    assert response.status_code == 422
    assert response.json()["error"] == "保存位置必须是绝对路径"


def test_direct_write_creates_missing_directory(tmp_path):
    """目录不存在时应被创建，而不是报错。"""
    target = tmp_path / "brand" / "new"
    payload = {
        "url": "https://example.com/video",
        "settings": {"directWrite": True, "outputDir": str(target)},
    }
    with patch.dict(os.environ, {"YTDLP_DESKTOP_TOKEN": "test-token"}):
        with TestClient(app) as client:
            with client.stream(
                "POST", "/api/download", json=payload, headers={"X-Desktop-Token": "test-token"}
            ) as response:
                assert response.status_code == 200
    assert target.is_dir()
