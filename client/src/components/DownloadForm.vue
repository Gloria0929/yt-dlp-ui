<script setup>
import { QUALITY_OPTIONS } from "../options.js";
import AdvancedSettings from "./AdvancedSettings.vue";

defineProps({
  modelValue: { type: String, default: "" },
  settings: { type: Object, required: true },
  urlCount: { type: Number, default: 0 },
  invalidCount: { type: Number, default: 0 },
  settingError: { type: String, default: "" },
  error: { type: String, default: "" },
  canRun: { type: Boolean, default: false },
  infoLoading: { type: Boolean, default: false },
  running: { type: Boolean, default: false },
  stopping: { type: Boolean, default: false },
  saveDirectoryName: { type: String, default: "" },
  directoryPickerSupported: { type: Boolean, default: false },
});

defineEmits([
  "update:modelValue",
  "reset",
  "extract",
  "download",
  "cancel",
  "select-directory",
]);
</script>

<template>
  <section class="composer" aria-labelledby="download-heading">
    <div class="section-index"></div>
    <div class="section-main">
      <div class="section-heading">
        <div>
          <p class="section-kicker">SOURCE</p>
          <h2 id="download-heading">下载内容</h2>
        </div>
        <button class="text-button" type="button" @click="$emit('reset')">
          清空
        </button>
      </div>

      <label class="url-field">
        <span class="sr-only">视频链接，每行一个</span>
        <textarea
          :value="modelValue"
          rows="4"
          spellcheck="false"
          placeholder="粘贴视频链接或整段分享文案&#10;支持 B 站、YouTube 与多个链接"
          @input="$emit('update:modelValue', $event.target.value)"
        ></textarea>
        <span class="url-count">{{
          urlCount ? `${urlCount} 个链接` : "支持批量"
        }}</span>
      </label>
      <p v-if="invalidCount" class="field-error">
        有 {{ invalidCount }} 个链接格式不正确
      </p>

      <div class="mode-row" aria-label="下载类型">
        <button
          type="button"
          :class="{ active: settings.mode === 'video' }"
          @click="settings.mode = 'video'"
        >
          <span class="mode-icon">▰</span>
          <span><strong>视频</strong><small>画面与声音</small></span>
        </button>
        <button
          type="button"
          :class="{ active: settings.mode === 'audio' }"
          @click="settings.mode = 'audio'"
        >
          <span class="mode-icon">◖</span>
          <span><strong>音频</strong><small>提取声音文件</small></span>
        </button>
      </div>

      <div v-if="settings.mode === 'video'" class="quality-block">
        <div class="field-heading">
          <span>画质</span><small>自动选择对应的最佳音轨</small>
        </div>
        <div class="quality-grid">
          <button
            v-for="quality in QUALITY_OPTIONS"
            :key="quality.value"
            type="button"
            :class="{ active: settings.quality === quality.value }"
            @click="settings.quality = quality.value"
          >
            <strong>{{ quality.label }}</strong>
            <small>{{ quality.hint }}</small>
          </button>
        </div>
      </div>

      <div v-else class="audio-row">
        <label>
          音频格式
          <select v-model="settings.audioFormat">
            <option value="mp3">MP3 · 通用</option>
            <option value="m4a">M4A · 原生</option>
            <option value="flac">FLAC · 无损</option>
            <option value="wav">WAV</option>
            <option value="opus">Opus</option>
          </select>
        </label>
      </div>

      <AdvancedSettings :settings="settings" :setting-error="settingError" />

      <div class="save-target">
        <div>
          <p>保存到本机</p>
          <strong>{{ saveDirectoryName || "浏览器下载目录" }}</strong>
          <small>
            {{
              saveDirectoryName
                ? "下载完成后直接写入这个文件夹"
                : "未选择文件夹时由浏览器处理保存位置"
            }}
          </small>
        </div>
        <button
          v-if="directoryPickerSupported"
          type="button"
          :disabled="running"
          @click="$emit('select-directory')"
        >
          {{ saveDirectoryName ? "更换文件夹" : "选择文件夹" }}
        </button>
      </div>

      <div v-if="error" class="error-box" role="alert">
        <span>!</span>
        <p>{{ error }}</p>
      </div>

      <div class="primary-actions">
        <button
          class="inspect-button"
          type="button"
          :disabled="!canRun || infoLoading || running"
          @click="$emit('extract')"
        >
          {{ infoLoading ? "正在解析…" : "读取视频信息" }}
        </button>
        <button
          v-if="!running"
          class="download-button"
          type="button"
          :disabled="!canRun || infoLoading"
          @click="$emit('download')"
        >
          <span>开始下载</span><b>↓</b>
        </button>
        <button
          v-else
          class="cancel-button"
          type="button"
          :disabled="stopping"
          @click="$emit('cancel')"
        >
          {{ stopping ? "正在停止…" : "取消下载" }}
        </button>
      </div>
    </div>
  </section>
</template>
