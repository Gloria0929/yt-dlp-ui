import test from "node:test";
import assert from "node:assert/strict";

import {
  buildArgs,
  formatCommand,
  initialState,
  parseUrls,
  validateSettings,
} from "./options.js";

test("parseUrls splits whitespace and removes duplicate links", () => {
  assert.deepEqual(
    parseUrls("https://example.com/a\nhttps://example.com/b https://example.com/a"),
    ["https://example.com/a", "https://example.com/b"],
  );
});

test("parseUrls extracts links from Bilibili share text", () => {
  assert.deepEqual(
    parseUrls(
      "【租几颗上亿元的卫星，能拍到什么？】 https://www.bilibili.com/video/BV1Pt3D6jEob/?share_source=copy_web",
    ),
    [
      "https://www.bilibili.com/video/BV1Pt3D6jEob/?share_source=copy_web",
    ],
  );
  assert.deepEqual(
    parseUrls("复制打开哔哩哔哩，看看这个视频 https://b23.tv/AbCd123。"),
    ["https://b23.tv/AbCd123"],
  );
});

test("video quality caps both merged and single-file fallbacks", () => {
  const state = initialState();
  state.quality = "1080";
  const args = buildArgs(state);
  assert.equal(args[args.indexOf("-f") + 1], "bv*[height<=1080]+ba/b[height<=1080]");
});

test("audio settings generate extraction arguments", () => {
  const state = initialState();
  state.mode = "audio";
  state.audioFormat = "flac";
  const args = buildArgs(state);
  assert.deepEqual(args.slice(args.indexOf("-f"), args.indexOf("-o")), [
    "-f",
    "bestaudio/best",
    "-x",
    "--audio-format",
    "flac",
    "--audio-quality",
    "0",
  ]);
});

test("common file, playlist and network settings are included", () => {
  const state = initialState();
  Object.assign(state, {
    playlist: true,
    playlistItems: "1:5",
    maxFilesize: "500M",
    rateLimit: "2M",
    concurrentFragments: 8,
    retries: 5,
    writeThumbnail: true,
    embedMetadata: true,
    writeInfoJson: true,
  });
  const command = buildArgs(state).join(" ");
  assert.match(command, /--yes-playlist --playlist-items 1:5/);
  assert.match(command, /--concurrent-fragments 8 --retries 5/);
  assert.match(command, /--write-thumbnail/);
  assert.match(command, /--embed-metadata/);
  assert.match(command, /--write-info-json/);
  assert.match(command, /--limit-rate 2M --max-filesize 500M/);
});

test("validation catches malformed common settings", () => {
  const state = initialState();
  state.proxy = "localhost:7890";
  assert.match(validateSettings(state), /代理地址/);
  state.proxy = "";
  state.playlist = true;
  state.playlistItems = "first five";
  assert.match(validateSettings(state), /播放列表范围/);
});

test("formatCommand quotes shell-sensitive URLs", () => {
  assert.equal(
    formatCommand(["https://example.com/watch?v=1&list=2"]),
    "yt-dlp 'https://example.com/watch?v=1&list=2'",
  );
});
