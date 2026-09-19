/** The UI deliberately exposes only everyday download settings. */
export const QUALITY_OPTIONS = [
  { value: 'best', label: '最佳画质', hint: '保留源视频最高质量' },
  { value: '1080', label: '1080p', hint: '全高清 · 日常推荐' },
  { value: '720', label: '720p', hint: '高清 · 节省空间' },
  { value: '480', label: '480p', hint: '标清 · 小体积' },
  { value: '2160', label: '4K', hint: '超高清 · 最大 2160p' },
];

export const OUTPUT_TEMPLATES = {
  'title-id': '%(title)s [%(id)s].%(ext)s',
  title: '%(title)s.%(ext)s',
  uploader: '%(uploader)s/%(title)s [%(id)s].%(ext)s',
  playlist: '%(playlist)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s',
};

export function initialState() {
  return {
    mode: 'video', quality: 'best', container: '', audioFormat: 'mp3',
    outputDir: '', fileNameTemplate: 'title-id', overwriteMode: 'resume',
    playlist: false, playlistItems: '',
    subtitles: 'none', subLangs: 'zh.*,en',
    embedSubs: false, proxy: '', cookiesFromBrowser: '', rateLimit: '',
    maxFilesize: '', concurrentFragments: 4, retries: 3,
    writeThumbnail: false, embedThumbnail: false,
    embedMetadata: false, writeInfoJson: false,
  };
}

export function parseUrls(text) {
  const matches = String(text || "").match(/https?:\/\/[^\s<>"'`]+/gi) || [];
  return [
    ...new Set(
      matches
        .map((url) => url.replace(/[，。；！？、）》】]+$/u, ""))
        .filter(Boolean),
    ),
  ];
}

export function isValidUrl(value) {
  try { return ['http:', 'https:'].includes(new URL(value).protocol); }
  catch { return false; }
}

export function validateSettings(state) {
  if (state.proxy.trim()) {
    try {
      const proxy = new URL(state.proxy.trim());
      if (!['http:', 'https:', 'socks4:', 'socks5:', 'socks5h:'].includes(proxy.protocol) || !proxy.hostname) throw new Error();
    } catch { return '代理地址需以 http://、https:// 或 socks5:// 等协议开头'; }
  }
  if (state.rateLimit.trim() && !/^\d+(?:\.\d+)?[KMG]?$/i.test(state.rateLimit.trim())) {
    return '限速格式不正确，请填写 500K、2M 或每秒字节数';
  }
  if (state.maxFilesize.trim() && !/^\d+(?:\.\d+)?[KMG]?$/i.test(state.maxFilesize.trim())) {
    return '最大文件大小格式不正确，请填写 500M、2G 或字节数';
  }
  if (state.playlist && state.playlistItems.trim() && !/^[0-9,:-]+$/.test(state.playlistItems.trim())) {
    return '播放列表范围格式不正确，请填写 1:5、1,3,7 或类似范围';
  }
  return '';
}

export function buildNetworkArgs(state) {
  const args = [];
  if (state.proxy.trim()) args.push('--proxy', state.proxy.trim());
  if (state.cookiesFromBrowser) args.push('--cookies-from-browser', state.cookiesFromBrowser);
  return args;
}

export function buildArgs(state) {
  const args = ['--ignore-config', '--newline', '--no-color', ...buildNetworkArgs(state)];
  args.push(state.playlist ? '--yes-playlist' : '--no-playlist');
  if (state.playlist && state.playlistItems.trim()) {
    args.push('--playlist-items', state.playlistItems.trim());
  }
  args.push('--concurrent-fragments', String(state.concurrentFragments));
  args.push('--retries', String(state.retries));
  if (state.mode === 'audio') {
    args.push('-f', 'bestaudio/best', '-x', '--audio-format', state.audioFormat, '--audio-quality', '0');
  } else {
    // Apply the height cap to BOTH branches, including pre-merged fallback formats.
    const cap = state.quality === 'best' ? '' : `[height<=${state.quality}]`;
    args.push('-f', `bv*${cap}+ba/b${cap}`);
    if (state.container) {
      args.push('--merge-output-format', state.container, '--remux-video', state.container);
      if (state.container === 'mp4') args.push('-S', 'vcodec:h264,acodec:aac');
    }
  }
  if (state.outputDir.trim()) args.push('-P', state.outputDir.trim());
  args.push('-o', OUTPUT_TEMPLATES[state.fileNameTemplate] || OUTPUT_TEMPLATES['title-id']);
  if (state.overwriteMode === 'skip') args.push('--no-overwrites');
  if (state.overwriteMode === 'overwrite') args.push('--force-overwrites');
  if (state.subtitles !== 'none') {
    args.push('--write-subs', '--sub-langs', state.subLangs.trim() || 'zh.*,en');
    if (state.subtitles === 'auto') args.push('--write-auto-subs');
    if (state.embedSubs && state.mode === 'video') args.push('--embed-subs');
  }
  if (state.writeThumbnail) args.push('--write-thumbnail');
  if (state.embedThumbnail) args.push('--embed-thumbnail');
  if (state.embedMetadata) args.push('--embed-metadata');
  if (state.writeInfoJson) args.push('--write-info-json');
  if (state.rateLimit.trim()) args.push('--limit-rate', state.rateLimit.trim());
  if (state.maxFilesize.trim()) args.push('--max-filesize', state.maxFilesize.trim());
  return args;
}

/** POSIX shell quoting: URLs containing &, templates, quotes and $ remain literal. */
export function shellQuote(value) {
  const text = String(value);
  return /^[a-zA-Z0-9_./:=+,-]+$/.test(text) ? text : "'" + text.replaceAll("'", "'\\''") + "'";
}
export function formatCommand(args) {
  return ['yt-dlp', ...args.map(shellQuote)].join(' ');
}
