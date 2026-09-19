"""Native yt_dlp integration. No yt-dlp CLI or shell command is executed."""
import os
import queue
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import yt_dlp
from server.models import DEFAULT_OUTPUT, Settings

OUTPUT_TEMPLATES = {
    'title-id': '%(title)s [%(id)s].%(ext)s',
    'title': '%(title)s.%(ext)s',
    'uploader': '%(uploader)s/%(title)s [%(id)s].%(ext)s',
    'playlist': '%(playlist)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s',
}


def output_directory(settings: Settings) -> str:
    return str(Path(settings.outputDir).expanduser().resolve() if settings.outputDir else DEFAULT_OUTPUT)


def prefer_bilibili_backup_urls(play_info):
    """Replace unreachable Bilibili PCDN endpoints with official backup CDNs."""
    dash = play_info.get('dash') or {}
    groups = [dash.get('video'), dash.get('audio')]
    groups.extend([
        (dash.get('dolby') or {}).get('audio'),
        [(dash.get('flac') or {}).get('audio')],
    ])
    changed = 0
    for streams in groups:
        for stream in streams or []:
            if not isinstance(stream, dict):
                continue
            current_key = 'baseUrl' if 'baseUrl' in stream else 'base_url'
            current = stream.get(current_key) or stream.get('url')
            host = (urlsplit(current).hostname or '') if current else ''
            if '.mcdn.bilivideo.cn' not in host:
                continue
            backups = stream.get('backupUrl') or stream.get('backup_url') or []
            replacement = next((
                url for url in backups
                if '.mcdn.bilivideo.cn' not in (urlsplit(url).hostname or '')
            ), None)
            if replacement:
                stream[current_key] = replacement
                changed += 1
    return changed


def enable_bilibili_cdn_fallback():
    # yt-dlp currently keeps Bilibili's first baseUrl and discards backupUrl.
    # Some networks cannot reach the PCDN host/port, while official backups work.
    from yt_dlp.extractor.bilibili import BilibiliBaseIE

    original = BilibiliBaseIE.extract_formats
    if getattr(original, '_frame_get_fallback', False):
        return

    def extract_formats(self, play_info):
        prefer_bilibili_backup_urls(play_info)
        return original(self, play_info)

    extract_formats._frame_get_fallback = True
    BilibiliBaseIE.extract_formats = extract_formats


def size_to_bytes(value):
    if not value:
        return None
    suffix = value[-1].upper()
    power = {'K': 1, 'M': 2, 'G': 3}.get(suffix, 0)
    number = value[:-1] if power else value
    return int(float(number) * 1024 ** power)


def build_options(settings: Settings, *, preview=False):
    options = {
        'quiet': True, 'no_warnings': False, 'noprogress': True,
        'ignoreconfig': True,
        'socket_timeout': 20,
        'retries': settings.retries,
        'fragment_retries': settings.retries,
        'concurrent_fragment_downloads': settings.concurrentFragments,
        'noplaylist': not settings.playlist,
    }
    # Node is common on this project's machines; enable it when Deno isn't installed.
    if shutil.which('node'):
        options['js_runtimes'] = {'node': {}}
    if settings.proxy:
        options['proxy'] = settings.proxy
    if settings.cookiesFromBrowser:
        options['cookiesfrombrowser'] = (settings.cookiesFromBrowser, None, None, None)
    if preview:
        # Preview must not inherit output, subtitle, codec or conversion restrictions.
        options.update(skip_download=True, noplaylist=True, playlist_items='1', ignore_no_formats_error=True)
        return options

    options.update({
        'paths': {'home': output_directory(settings)},
        'outtmpl': {'default': OUTPUT_TEMPLATES[settings.fileNameTemplate]},
        'writethumbnail': settings.writeThumbnail or settings.embedThumbnail,
        'writeinfojson': settings.writeInfoJson,
    })
    if settings.playlist and settings.playlistItems:
        options['playlist_items'] = settings.playlistItems
    if settings.overwriteMode == 'skip':
        options['overwrites'] = False
    elif settings.overwriteMode == 'overwrite':
        options['overwrites'] = True
    if settings.maxFilesize:
        options['max_filesize'] = size_to_bytes(settings.maxFilesize)
    processors = []
    if settings.mode == 'audio':
        options['format'] = 'bestaudio/best'
        processors.append({'key': 'FFmpegExtractAudio', 'preferredcodec': settings.audioFormat, 'preferredquality': '0'})
    else:
        cap = '' if settings.quality == 'best' else f'[height<={settings.quality}]'
        options['format'] = f'bv*{cap}+ba/b{cap}'
        if settings.container:
            options['merge_output_format'] = settings.container
            processors.append({'key': 'FFmpegVideoRemuxer', 'preferedformat': settings.container})
            if settings.container == 'mp4':
                options['format_sort'] = ['vcodec:h264', 'acodec:aac']
    if settings.subtitles != 'none':
        options['writesubtitles'] = True
        options['writeautomaticsub'] = settings.subtitles == 'auto'
        options['subtitleslangs'] = [s.strip() for s in (settings.subLangs or 'zh.*,en').split(',') if s.strip()]
        if settings.embedSubs and settings.mode == 'video':
            processors.append({'key': 'FFmpegEmbedSubtitle'})
    if settings.embedMetadata:
        processors.append({'key': 'FFmpegMetadata'})
    if settings.embedThumbnail:
        processors.append({'key': 'EmbedThumbnail'})
    if settings.rateLimit:
        options['ratelimit'] = size_to_bytes(settings.rateLimit)
    options['postprocessors'] = processors
    return options


def friendly_error(error):
    message = str(error).removeprefix('ERROR: ').strip()
    if 'CERTIFICATE_VERIFY_FAILED' in message or 'certificate verify failed' in message:
        return 'TLS 证书校验失败。请更新 Python 的 certifi 证书，或检查代理的 HTTPS 证书。\n' + message
    if 'Sign in' in message or 'cookies' in message.lower() or '403' in message:
        return '站点可能需要登录或限制访问。请在更多设置中选择已登录的浏览器，必要时设置代理。\n' + message
    if 'Unsupported URL' in message:
        return '暂不支持该链接，请使用视频详情页或视频文件地址。\n' + message
    if 'Requested format is not available' in message:
        return '当前画质不可用。请降低画质，或在更多设置中读取已登录浏览器的状态后重试。\n' + message
    if 'timed out' in message or 'Unable to download' in message:
        return '无法连接视频站点，请检查网络和代理设置。\n' + message
    return message or '下载引擎返回了未知错误'


def summarize_info(info):
    if info.get('_type') in ('playlist', 'multi_video') or 'entries' in info:
        info = next((entry for entry in info.get('entries', []) if entry), None)
        if not info:
            raise ValueError('播放列表中没有可解析的视频')
    keys = ('id', 'title', 'thumbnail', 'duration', 'uploader', 'channel', 'webpage_url', 'extractor', 'upload_date')
    result = {key: info.get(key) for key in keys}
    result['formats'] = [
        {key: f.get(key) for key in ('format_id', 'ext', 'width', 'height', 'fps', 'filesize', 'filesize_approx', 'vcodec', 'acodec')}
        for f in info.get('formats', []) if f.get('ext') != 'mhtml'
    ]
    return result


def media_worker(action, url, settings_data, events):
    """An isolated Python worker makes cancel/disconnect stop network and ffmpeg work."""
    if os.name == 'posix':
        os.setsid()

    def emit(event, terminal=False):
        try:
            events.put(event, block=terminal, timeout=5 if terminal else None)
        except queue.Full:
            pass  # A slow client may skip intermediate logs; terminal events are retained.

    class Logger:
        def debug(self, message):
            if not message.startswith('[debug] '):
                emit({'type': 'log', 'line': message, 'level': 'info'})
        def info(self, message):
            self.debug(message)
        def warning(self, message):
            emit({'type': 'log', 'line': message, 'level': 'warning'})
        def error(self, message):
            emit({'type': 'log', 'line': message, 'level': 'error'})

    def progress(data):
        info = data.get('info_dict') or {}
        total = data.get('total_bytes') or data.get('total_bytes_estimate')
        downloaded = data.get('downloaded_bytes') or 0
        emit({
            'type': 'progress', 'phase': data['status'],
            'percent': min(100, downloaded / total * 100) if total else None,
            'downloaded': downloaded, 'total': total, 'speed': data.get('speed'),
            'eta': data.get('eta'), 'title': info.get('title'),
            'filename': data.get('filename'), 'playlistIndex': info.get('playlist_index'),
        })

    def postprocess(data):
        emit({'type': 'processing', 'processor': data.get('postprocessor'), 'phase': data.get('status')})

    try:
        enable_bilibili_cdn_fallback()
        settings = Settings.model_validate(settings_data)
        options = build_options(settings, preview=action == 'info')
        options.update(logger=Logger(), progress_hooks=[progress], postprocessor_hooks=[postprocess])
        with yt_dlp.YoutubeDL(options) as downloader:
            if action == 'info':
                info = downloader.extract_info(url, download=False)
                if not info:
                    raise ValueError('未获取到视频信息')
                emit({'type': 'info', 'info': summarize_info(info)}, terminal=True)
            else:
                code = downloader.download([url])
                emit({'type': 'done', 'code': code}, terminal=True)
    except Exception as error:
        emit({'type': 'error', 'error': friendly_error(error)}, terminal=True)
