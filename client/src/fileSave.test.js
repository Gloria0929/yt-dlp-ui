import test from "node:test";
import assert from "node:assert/strict";

import {
  safePathParts,
  saveFileToDirectory,
  supportsDirectoryPicker,
} from "./fileSave.js";

test("safePathParts preserves folders and removes traversal segments", () => {
  assert.deepEqual(safePathParts("channel/../video.mp4"), [
    "channel",
    "video.mp4",
  ]);
});

test("directory picker support is feature-detected", () => {
  assert.equal(supportsDirectoryPicker({ showDirectoryPicker() {} }), true);
  assert.equal(supportsDirectoryPicker({}), false);
});

test("download response streams into the selected local directory", async () => {
  let written = "";
  const writable = new WritableStream({
    write(chunk) {
      written += new TextDecoder().decode(chunk);
    },
  });
  const fileHandle = { async createWritable() { return writable; } };
  const childDirectory = {
    async getFileHandle(name, options) {
      assert.equal(name, "video.mp4");
      assert.deepEqual(options, { create: true });
      return fileHandle;
    },
  };
  const rootDirectory = {
    async getDirectoryHandle(name, options) {
      assert.equal(name, "channel");
      assert.deepEqual(options, { create: true });
      return childDirectory;
    },
  };

  const result = await saveFileToDirectory(
    {
      name: "video.mp4",
      relativePath: "channel/video.mp4",
      downloadUrl: "/api/files/task/file",
    },
    rootDirectory,
    { fetcher: async () => new Response("media") },
  );

  assert.deepEqual(result, { skipped: false });
  assert.equal(written, "media");
});
