export function supportsDirectoryPicker(scope = globalThis) {
  return typeof scope?.showDirectoryPicker === "function";
}

export async function chooseDirectory(scope = globalThis) {
  if (!supportsDirectoryPicker(scope)) return null;
  return scope.showDirectoryPicker({ mode: "readwrite", startIn: "downloads" });
}

export function safePathParts(relativePath, fallbackName = "download") {
  const parts = String(relativePath || fallbackName)
    .split(/[\\/]+/)
    .map((part) => part.trim())
    .filter((part) => part && part !== "." && part !== "..");
  return parts.length ? parts : [fallbackName];
}

async function canWrite(directoryHandle) {
  if (typeof directoryHandle.queryPermission !== "function") return true;
  const options = { mode: "readwrite" };
  if ((await directoryHandle.queryPermission(options)) === "granted") return true;
  return (await directoryHandle.requestPermission(options)) === "granted";
}

async function targetFileHandle(directoryHandle, file, overwriteMode) {
  const parts = safePathParts(file.relativePath, file.name);
  const fileName = parts.pop();
  let parent = directoryHandle;
  for (const directory of parts) {
    parent = await parent.getDirectoryHandle(directory, { create: true });
  }
  if (overwriteMode === "skip") {
    try {
      await parent.getFileHandle(fileName);
      return null;
    } catch (error) {
      if (error?.name !== "NotFoundError") throw error;
    }
  }
  return parent.getFileHandle(fileName, { create: true });
}

export async function saveFileToDirectory(
  file,
  directoryHandle,
  { signal, overwriteMode = "resume", fetcher = fetch } = {},
) {
  if (!(await canWrite(directoryHandle))) {
    throw new Error("没有本机目录写入权限，请重新选择保存目录");
  }
  const fileHandle = await targetFileHandle(
    directoryHandle,
    file,
    overwriteMode,
  );
  if (!fileHandle) return { skipped: true };

  const response = await fetcher(file.downloadUrl, { signal });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `文件传输失败（${response.status}）`);
  }
  const writable = await fileHandle.createWritable();
  try {
    await response.body.pipeTo(writable, { signal });
  } catch (error) {
    if (typeof writable.abort === "function") {
      await writable.abort().catch(() => {});
    }
    throw error;
  }
  return { skipped: false };
}

export function triggerBrowserDownload(file, documentRef = document) {
  const anchor = documentRef.createElement("a");
  anchor.href = file.downloadUrl;
  anchor.download = file.name;
  anchor.hidden = true;
  documentRef.body.append(anchor);
  anchor.click();
  anchor.remove();
}
