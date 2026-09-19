<script setup>
import { computed, onMounted, reactive, ref, shallowRef, watch } from "vue";
import AppHeader from "./components/AppHeader.vue";
import DownloadForm from "./components/DownloadForm.vue";
import MediaPanel from "./components/MediaPanel.vue";
import ToastNotice from "./components/ToastNotice.vue";
import {
  buildArgs,
  formatCommand,
  initialState,
  isValidUrl,
  parseUrls,
  validateSettings,
} from "./options.js";
import { consumeEvents } from "./stream.js";
import {
  chooseDirectory,
  saveFileToDirectory,
  supportsDirectoryPicker,
  triggerBrowserDownload,
} from "./fileSave.js";

const urlText = ref("");
const settings = reactive(initialState());
const health = ref(null);
const info = ref(null);
const infoLoading = ref(false);
const running = ref(false);
const stopping = ref(false);
const currentIndex = ref(0);
const progress = ref(0);
const taskTitle = ref("");
const speed = ref("");
const eta = ref("");
const status = ref("等待任务");
const logs = ref([]);
const error = ref("");
const toast = ref("");
const theme = ref("paper");
const directoryPickerSupported = ref(false);
const directoryHandle = shallowRef(null);
let controller = null;
let toastTimer = null;

const urls = computed(() => parseUrls(urlText.value));
const invalidUrls = computed(() =>
  urls.value.filter((url) => !isValidUrl(url)),
);
const primaryUrl = computed(() => urls.value[0] || "");
const args = computed(() => buildArgs(settings));
const command = computed(() => formatCommand([...args.value, ...urls.value]));
const settingError = computed(() => validateSettings(settings));
const canRun = computed(
  () =>
    urls.value.length > 0 &&
    !invalidUrls.value.length &&
    !settingError.value &&
    health.value?.ok,
);
const percentage = computed(() =>
  Math.max(0, Math.min(100, Number(progress.value) || 0)),
);
const videoMeta = computed(() => {
  if (!info.value) return [];
  return [
    info.value.uploader || info.value.channel,
    formatDuration(info.value.duration),
    formatUploadDate(info.value.upload_date),
    info.value.extractor,
  ].filter(Boolean);
});
const saveDirectoryName = computed(() => directoryHandle.value?.name || "");

watch(urlText, () => {
  info.value = null;
  error.value = "";
});

watch(theme, (value) => {
  document.documentElement.dataset.theme = value;
  localStorage.setItem("frame-get-theme", value);
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", value === "dark" ? "#111210" : "#f1ede3");
});

function notify(message) {
  toast.value = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (toast.value = ""), 2400);
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return "";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = Math.floor(seconds % 60);
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`
    : `${minutes}:${String(rest).padStart(2, "0")}`;
}

function formatUploadDate(value) {
  const date = String(value || "");
  if (!/^\d{8}$/.test(date)) return "";
  return `发布于 ${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
}

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size < 10 && unit ? 1 : 0)} ${units[unit]}`;
}

function friendlyHttpError(response, data) {
  if (data?.error) return data.error;
  if (response.status === 429) return "当前任务较多，请稍后重试";
  return `服务请求失败（${response.status}）`;
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    health.value = response.ok ? await response.json() : null;
  } catch {
    health.value = null;
  }
}

async function extractInfo() {
  if (!canRun.value) {
    error.value = invalidUrls.value.length
      ? "链接格式不正确，请检查后重试"
      : settingError.value || "请先粘贴视频链接";
    return;
  }
  infoLoading.value = true;
  error.value = "";
  info.value = null;
  controller?.abort();
  controller = new AbortController();
  try {
    const response = await fetch("/api/extract-info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ url: primaryUrl.value, settings }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(friendlyHttpError(response, data));
    info.value = data.info;
    notify("视频信息已读取");
  } catch (requestError) {
    if (requestError.name !== "AbortError") error.value = requestError.message;
  } finally {
    infoLoading.value = false;
    controller = null;
  }
}

function addLog(line, level = "info") {
  if (!line?.trim()) return;
  logs.value.push({
    line: line.trim(),
    level,
    time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
  });
  if (logs.value.length > 300) logs.value.splice(0, logs.value.length - 300);
}

async function discardReadyFile(file) {
  await fetch(file.downloadUrl, { method: "DELETE" }).catch(() => {});
}

async function saveReadyFiles(files) {
  if (!files?.length) throw new Error("下载完成，但服务端没有返回文件");
  if (directoryHandle.value) {
    for (const file of files) {
      const result = await saveFileToDirectory(file, directoryHandle.value, {
        signal: controller?.signal,
        overwriteMode: settings.overwriteMode,
      });
      if (result.skipped) {
        await discardReadyFile(file);
        addLog(`已跳过本机同名文件 · ${file.relativePath}`, "warning");
      } else {
        addLog(`已保存到 ${directoryHandle.value.name}/${file.relativePath}`, "success");
      }
    }
    return;
  }
  files.forEach((file) => triggerBrowserDownload(file));
  addLog(
    `${files.length} 个文件已交给浏览器，请在浏览器下载列表中查看`,
    "success",
  );
}

async function handleEvent(event) {
  if (event.type === "progress") {
    if (event.percent != null) progress.value = event.percent;
    taskTitle.value = event.title || taskTitle.value;
    speed.value = event.speed ? `${formatBytes(event.speed)}/s` : "";
    eta.value = Number.isFinite(event.eta) ? `${event.eta}s` : "";
    status.value = event.phase === "finished" ? "正在合并与处理" : "正在下载";
  } else if (event.type === "processing") {
    status.value =
      event.phase === "started"
        ? `正在处理 · ${event.processor || "媒体文件"}`
        : status.value;
  } else if (event.type === "log") {
    addLog(event.line, event.level);
  } else if (event.type === "error") {
    throw new Error(event.error);
  } else if (event.type === "done") {
    status.value = "正在保存到本机";
    await saveReadyFiles(event.files);
    progress.value = 100;
    status.value = "本条下载完成";
  }
}

async function downloadOne(url) {
  const response = await fetch("/api/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: controller.signal,
    body: JSON.stringify({ url, settings }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(friendlyHttpError(response, data));
  }
  await consumeEvents(response.body, handleEvent);
}

async function startDownload() {
  if (!canRun.value || running.value) {
    error.value = invalidUrls.value.length
      ? "存在格式不正确的链接"
      : settingError.value || "请先粘贴视频链接";
    return;
  }
  running.value = true;
  stopping.value = false;
  error.value = "";
  logs.value = [];
  controller = new AbortController();
  try {
    for (let index = 0; index < urls.value.length; index += 1) {
      if (controller.signal.aborted) break;
      currentIndex.value = index;
      progress.value = 0;
      speed.value = "";
      eta.value = "";
      taskTitle.value = `任务 ${index + 1}`;
      status.value = "正在连接视频站点";
      addLog(
        `开始任务 ${index + 1}/${urls.value.length} · ${urls.value[index]}`,
      );
      await downloadOne(urls.value[index]);
    }
    if (!controller.signal.aborted) {
      status.value =
        urls.value.length > 1
          ? `${urls.value.length} 个任务全部完成`
          : "下载完成";
      notify("下载完成");
    }
  } catch (requestError) {
    if (requestError.name === "AbortError") {
      status.value = "任务已取消";
      addLog("已取消当前任务", "warning");
    } else {
      error.value = requestError.message;
      status.value = "下载失败";
      addLog(requestError.message, "error");
    }
  } finally {
    running.value = false;
    stopping.value = false;
    controller = null;
  }
}

function cancelDownload() {
  if (!controller) return;
  stopping.value = true;
  status.value = "正在停止任务";
  controller.abort();
}

async function copyCommand() {
  try {
    await navigator.clipboard.writeText(command.value);
    notify("命令已复制");
  } catch {
    error.value = "浏览器未允许复制，请手动选择命令文本";
  }
}

async function selectSaveDirectory() {
  try {
    const selected = await chooseDirectory(window);
    if (selected) {
      directoryHandle.value = selected;
      notify(`保存位置：${selected.name}`);
    }
  } catch (pickerError) {
    if (pickerError.name !== "AbortError") {
      error.value = pickerError.message || "无法选择本机目录";
    }
  }
}

function toggleTheme() {
  theme.value = theme.value === "paper" ? "dark" : "paper";
}

function reset() {
  if (running.value) cancelDownload();
  urlText.value = "";
  Object.assign(settings, initialState());
  info.value = null;
  logs.value = [];
  error.value = "";
  progress.value = 0;
  status.value = "等待任务";
}

onMounted(() => {
  const savedTheme = localStorage.getItem("frame-get-theme");
  theme.value = savedTheme === "dark" ? "dark" : "paper";
  document.documentElement.dataset.theme = theme.value;
  directoryPickerSupported.value = supportsDirectoryPicker(window);
  loadHealth();
});
</script>

<template>
  <div class="shell">
    <AppHeader :health="health" :theme="theme" @toggle-theme="toggleTheme" />

    <main id="main">
      <section class="intro">
        <p class="eyebrow">YT-DLP DOWNLOAD DESK</p>
        <h1>贴上链接，<br /><em>把视频带走。</em></h1>
        <p class="intro-copy">
          支持视频、音频、字幕与多个链接队列，下载过程实时可见。
        </p>
      </section>

      <div class="workspace">
        <DownloadForm
          v-model="urlText"
          :settings="settings"
          :url-count="urls.length"
          :invalid-count="invalidUrls.length"
          :setting-error="settingError"
          :error="error"
          :can-run="canRun"
          :info-loading="infoLoading"
          :running="running"
          :stopping="stopping"
          :save-directory-name="saveDirectoryName"
          :directory-picker-supported="directoryPickerSupported"
          @reset="reset"
          @extract="extractInfo"
          @download="startDownload"
          @cancel="cancelDownload"
          @select-directory="selectSaveDirectory"
        />
        <MediaPanel
          :info="info"
          :info-loading="infoLoading"
          :video-meta="videoMeta"
          :running="running"
          :percentage="percentage"
          :status="status"
          :url-count="urls.length"
          :current-index="currentIndex"
          :task-title="taskTitle"
          :speed="speed"
          :eta="eta"
          :logs="logs"
          :command="command"
          @copy-command="copyCommand"
        />
      </div>
    </main>

    <footer>
      <span>FRAME/GET</span><span>FASTAPI + NATIVE YT_DLP</span
      ><span>文件保存在本机</span>
    </footer>
    <ToastNotice :message="toast" />
  </div>
</template>
