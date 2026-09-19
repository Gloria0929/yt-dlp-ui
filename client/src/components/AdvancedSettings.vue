<script setup>
defineProps({
  settings: { type: Object, required: true },
  settingError: { type: String, default: "" },
});
</script>

<template>
  <details class="advanced">
    <summary>
      <span>更多设置</span><small>文件、播放列表、媒体与网络</small>
    </summary>
    <div class="advanced-grid">
      <p class="advanced-label">文件与播放列表</p>
      <label>
        文件名规则
        <select v-model="settings.fileNameTemplate">
          <option value="title-id">标题 [视频 ID]</option>
          <option value="title">仅标题</option>
          <option value="uploader">上传者 / 标题 [视频 ID]</option>
          <option value="playlist">播放列表 / 序号 - 标题</option>
        </select>
      </label>
      <label>
        已有文件
        <select v-model="settings.overwriteMode">
          <option value="resume">自动覆盖同名文件</option>
          <option value="skip">跳过本机同名文件</option>
          <option value="overwrite">强制覆盖</option>
        </select>
      </label>
      <label>
        最大文件大小
        <input v-model="settings.maxFilesize" placeholder="留空不限，例如 500M" />
      </label>
      <div class="check-list full-width">
        <label>
          <input v-model="settings.playlist" type="checkbox" />
          <span>下载整个播放列表</span>
        </label>
      </div>
      <label v-if="settings.playlist">
        播放列表范围
        <input v-model="settings.playlistItems" placeholder="例如 1:5 或 1,3,7" />
      </label>

      <p class="advanced-label">媒体内容</p>
      <label v-if="settings.mode === 'video'">
        封装格式
        <select v-model="settings.container">
          <option value="">自动选择</option>
          <option value="mp4">MP4</option>
          <option value="mkv">MKV</option>
        </select>
      </label>
      <label>
        字幕
        <select v-model="settings.subtitles">
          <option value="none">不下载</option>
          <option value="manual">人工字幕</option>
          <option value="auto">人工 + 自动字幕</option>
        </select>
      </label>
      <label v-if="settings.subtitles !== 'none'">
        字幕语言
        <input v-model="settings.subLangs" placeholder="zh.*,en" />
      </label>
      <div class="check-list full-width">
        <label v-if="settings.subtitles !== 'none' && settings.mode === 'video'">
          <input v-model="settings.embedSubs" type="checkbox" />
          <span>字幕嵌入视频</span>
        </label>
        <label>
          <input v-model="settings.writeThumbnail" type="checkbox" />
          <span>单独保存封面</span>
        </label>
        <label>
          <input v-model="settings.embedThumbnail" type="checkbox" />
          <span>封面嵌入文件</span>
        </label>
        <label>
          <input v-model="settings.embedMetadata" type="checkbox" />
          <span>写入媒体信息</span>
        </label>
        <label>
          <input v-model="settings.writeInfoJson" type="checkbox" />
          <span>保存信息 JSON</span>
        </label>
      </div>

      <p class="advanced-label">网络与稳定性</p>
      <label>
        浏览器登录状态
        <select v-model="settings.cookiesFromBrowser">
          <option value="">不读取</option>
          <option value="chrome">Chrome</option>
          <option value="edge">Edge</option>
          <option value="firefox">Firefox</option>
          <option value="safari">Safari</option>
          <option value="brave">Brave</option>
        </select>
      </label>
      <label>
        代理
        <input v-model="settings.proxy" placeholder="例如 http://127.0.0.1:7890" />
      </label>
      <label>
        下载限速
        <input v-model="settings.rateLimit" placeholder="例如 2M" />
      </label>
      <label>
        并发分片
        <select v-model.number="settings.concurrentFragments">
          <option :value="1">1 · 稳定</option>
          <option :value="4">4 · 推荐</option>
          <option :value="8">8 · 更快</option>
          <option :value="16">16 · 高速网络</option>
        </select>
      </label>
      <label>
        失败重试
        <select v-model.number="settings.retries">
          <option :value="0">不重试</option>
          <option :value="3">3 次</option>
          <option :value="5">5 次</option>
          <option :value="10">10 次</option>
          <option :value="20">20 次</option>
        </select>
      </label>
    </div>
    <p v-if="settingError" class="field-error">{{ settingError }}</p>
  </details>
</template>
