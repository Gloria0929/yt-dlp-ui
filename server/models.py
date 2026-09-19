from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / 'downloads'


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['video', 'audio'] = 'video'
    quality: Literal['best', '480', '720', '1080', '2160'] = 'best'
    container: Literal['', 'mp4', 'mkv'] = ''
    audioFormat: Literal['mp3', 'm4a', 'flac', 'wav', 'opus'] = 'mp3'
    outputDir: str = Field(default='', max_length=4096)
    fileNameTemplate: Literal['title-id', 'title', 'uploader', 'playlist'] = 'title-id'
    overwriteMode: Literal['resume', 'skip', 'overwrite'] = 'resume'
    playlist: bool = False
    playlistItems: str = Field(default='', max_length=200)
    subtitles: Literal['none', 'manual', 'auto'] = 'none'
    subLangs: str = Field(default='zh.*,en', max_length=200)
    embedSubs: bool = False
    proxy: str = Field(default='', max_length=2048)
    cookiesFromBrowser: Literal['', 'chrome', 'edge', 'firefox', 'safari', 'brave', 'chromium'] = ''
    rateLimit: str = Field(default='', max_length=32)
    maxFilesize: str = Field(default='', max_length=32)
    concurrentFragments: int = Field(default=4, ge=1, le=16)
    retries: int = Field(default=3, ge=0, le=20)
    writeThumbnail: bool = False
    embedThumbnail: bool = False
    embedMetadata: bool = False
    writeInfoJson: bool = False

    @field_validator(
        'outputDir', 'proxy', 'rateLimit', 'maxFilesize',
        'subLangs', 'playlistItems',
    )
    @classmethod
    def trim(cls, value):
        if '\x00' in value:
            raise ValueError('内容不能包含空字符')
        return value.strip()

    @field_validator('proxy')
    @classmethod
    def valid_proxy(cls, value):
        if value:
            try:
                parsed = urlparse(value)
                if parsed.scheme not in ('http', 'https', 'socks4', 'socks5', 'socks5h') or not parsed.hostname:
                    raise ValueError()
                _ = parsed.port
            except ValueError:
                raise ValueError('代理地址格式不正确')
        return value

    @field_validator('rateLimit', 'maxFilesize')
    @classmethod
    def valid_rate(cls, value):
        if value and (not re.fullmatch(r'\d+(?:\.\d+)?[KMG]?', value, re.I) or float(value.rstrip('KkMmGg')) <= 0):
            raise ValueError('大小需为正数，例如 500M 或 2G')
        return value

    @field_validator('playlistItems')
    @classmethod
    def valid_playlist_items(cls, value):
        if value and not re.fullmatch(r'[0-9,:-]+', value):
            raise ValueError('播放列表范围格式不正确')
        return value


class MediaRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=1, max_length=8192)
    settings: Settings = Field(default_factory=Settings)

    @field_validator('url')
    @classmethod
    def valid_url(cls, value):
        value = value.strip()
        try:
            parsed = urlparse(value)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or re.search(r'\s', value):
                raise ValueError()
            _ = parsed.port
        except ValueError:
            raise ValueError('请填写有效的 http:// 或 https:// 视频链接')
        return value
