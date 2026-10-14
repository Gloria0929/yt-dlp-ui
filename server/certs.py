"""为 yt-dlp 提供合并后的 CA 证书包。

macOS 上 Python 的默认证书链来自 openssl 的 cert.pem 或 certifi 内置的 Mozilla 根证书，
两者都不包含用户自己安装的代理根证书（例如 Quantumult X、Proxyman、Charles）。
浏览器与 curl 走系统钥匙串，所以网页能打开，yt-dlp 却报 CERTIFICATE_VERIFY_FAILED。

这里把 certifi 内置证书与 macOS 钥匙串中的证书合并成一个 PEM，供 yt-dlp 使用。
没有额外安装代理证书的机器上，合并结果等价于 certifi 原文件，不会放宽信任范围。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import certifi

BUNDLE_ENV = "YTDLP_CA_BUNDLE"

_MAC_KEYCHAINS = (
    "/System/Library/Keychains/SystemRootCertificates.keychain",
    "/Library/Keychains/System.keychain",
    str(Path.home() / "Library" / "Keychains" / "login.keychain-db"),
)

_installed: Path | None = None


def _pem_blocks(data: bytes) -> list[bytes]:
    """按 PEM 边界切分证书块，忽略无关文本。"""
    blocks: list[bytes] = []
    begin = b"-----BEGIN CERTIFICATE-----"
    end = b"-----END CERTIFICATE-----"
    cursor = 0
    while True:
        start = data.find(begin, cursor)
        if start < 0:
            return blocks
        stop = data.find(end, start)
        if stop < 0:
            return blocks
        stop += len(end)
        blocks.append(data[start:stop] + b"\n")
        cursor = stop


def _keychain_blocks() -> list[bytes]:
    """读取 macOS 钥匙串中的证书；其他平台返回空列表。"""
    if sys.platform != "darwin":
        return []
    blocks: list[bytes] = []
    for keychain in _MAC_KEYCHAINS:
        if not Path(keychain).exists():
            continue
        try:
            result = subprocess.run(
                ["security", "find-certificate", "-a", "-p", keychain],
                capture_output=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            blocks.extend(_pem_blocks(result.stdout))
    return blocks


def _merge_blocks() -> list[bytes]:
    """合并 certifi 与钥匙串证书，按内容去重，保持稳定顺序。"""
    blocks: list[bytes] = []
    seen: set[str] = set()
    candidates = _pem_blocks(Path(certifi.where()).read_bytes()) + _keychain_blocks()
    for block in candidates:
        digest = hashlib.sha256(block).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        blocks.append(block)
    return blocks


def build_bundle(destination: Path) -> Path:
    """把合并后的证书写入 destination（先写临时文件再替换，避免并发读到半截文件）。"""
    blocks = _merge_blocks()
    if not blocks:
        raise RuntimeError("没有可用的 CA 证书")
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(destination.parent), prefix=".ca-bundle-")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(b"".join(blocks))
        os.replace(temp_name, destination)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return destination


def install_ca_bundle() -> Path | None:
    """构建并启用合并证书包，返回其路径；失败时返回 None 且不改变现有行为。"""
    global _installed
    if _installed is not None and _installed.is_file():
        return _installed
    try:
        cached = os.environ.get(BUNDLE_ENV)
        if cached and Path(cached).is_file():
            target = Path(cached)
        else:
            target = build_bundle(Path(tempfile.gettempdir()) / "frame-get-ca-bundle.pem")
            os.environ[BUNDLE_ENV] = str(target)
        # yt-dlp 只通过 certifi.where() 取证书，因此把该函数指向合并包即可生效。
        certifi.where = lambda: str(target)  # type: ignore[assignment]
        for name in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS"):
            os.environ.setdefault(name, str(target))
    except Exception:
        return None
    _installed = target
    return target
