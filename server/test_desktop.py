"""Desktop-only API authentication and packaged frontend contract."""
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.app import app


def test_desktop_api_requires_launch_token():
    with patch.dict(os.environ, {"YTDLP_DESKTOP_TOKEN": "test-session-token"}):
        with TestClient(app) as client:
            denied = client.get("/api/health")
            assert denied.status_code == 403
            assert denied.json()["error"] == "拒绝访问桌面应用的本地服务"
            allowed = client.get("/api/health", headers={"X-Desktop-Token": "test-session-token"})
            assert allowed.status_code == 200
            assert allowed.json()["ok"] is True


def test_browser_api_still_works_without_desktop_token():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("YTDLP_DESKTOP_TOKEN", None)
        with TestClient(app) as client:
            response = client.get("/api/health")
            assert response.status_code == 200
            assert response.json()["engine"] == "yt_dlp"
