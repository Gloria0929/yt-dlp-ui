"""合并证书包：包含 certifi 全部证书，且失败时不改变原有行为。"""
import certifi
from pathlib import Path

from server.certs import _pem_blocks, build_bundle


def test_bundle_contains_every_certifi_certificate(tmp_path):
    destination = tmp_path / "ca.pem"
    build_bundle(destination)
    bundled = set(_pem_blocks(destination.read_bytes()))
    for block in _pem_blocks(Path(certifi.where()).read_bytes()):
        assert block in bundled


def test_bundle_is_deduplicated(tmp_path):
    destination = tmp_path / "ca.pem"
    build_bundle(destination)
    blocks = _pem_blocks(destination.read_bytes())
    assert len(blocks) == len(set(blocks))


def test_bundle_replaces_atomically(tmp_path):
    destination = tmp_path / "nested" / "ca.pem"
    build_bundle(destination)
    assert destination.is_file()
    assert not list(destination.parent.glob(".ca-bundle-*"))
