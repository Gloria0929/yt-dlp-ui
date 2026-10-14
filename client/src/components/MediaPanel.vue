<script setup>
import { nextTick, ref, watch } from "vue";

const props = defineProps({
  info: { type: Object, default: null },
  infoLoading: { type: Boolean, default: false },
  videoMeta: { type: Array, default: () => [] },
  running: { type: Boolean, default: false },
  savingFiles: { type: Boolean, default: false },
  percentage: { type: Number, default: 0 },
  status: { type: String, default: "" },
  urlCount: { type: Number, default: 0 },
  currentIndex: { type: Number, default: 0 },
  taskTitle: { type: String, default: "" },
  speed: { type: String, default: "" },
  eta: { type: String, default: "" },
  logs: { type: Array, default: () => [] },
  command: { type: String, default: "" },
  savedFiles: { type: Array, default: () => [] },
  desktop: { type: Boolean, default: false },
});

defineEmits(["copy-command", "reveal-file"]);

const logView = ref(null);

watch(
  () => props.logs.length,
  async () => {
    await nextTick();
    if (logView.value) {
      logView.value.scrollTop = logView.value.scrollHeight;
    }
  },
  { flush: "post" },
);
</script>

<template>
  <aside class="side-panel" aria-label="预览与任务状态">
    <article v-if="info" class="media-card">
      <div class="poster">
        <img
          v-if="info.thumbnail"
          :src="info.thumbnail"
          :alt="`${info.title} 封面`"
          referrerpolicy="no-referrer"
        />
        <span v-else>NO PREVIEW</span>
      </div>
      <div class="media-copy">
        <p>READY TO DOWNLOAD</p>
        <h3>{{ info.title }}</h3>
        <div class="meta">
          <span v-for="item in videoMeta" :key="item">{{ item }}</span>
        </div>
      </div>
    </article>

    <article v-else-if="infoLoading" class="empty-preview loading-preview" aria-label="正在读取视频信息">
      <div class="preview-skeleton"></div>
      <div class="skeleton-line"></div>
      <div class="skeleton-line short"></div>
      <p class="loading-caption">正在连接视频站点并读取封面…</p>
    </article>

    <article v-else class="empty-preview">
      <div class="preview-art" aria-hidden="true">
        <span>
          <svg viewBox="0 0 24 24" focusable="false">
            <path d="M8 5.75v12.5L18 12 8 5.75Z" />
          </svg>
        </span>
      </div>
      <p>视频预览</p>
      <h3>读取后会在这里显示标题与封面</h3>
    </article>

    <article
      class="task-card"
      :class="{ active: running, complete: !running && percentage === 100 }"
      role="status"
    >
      <div class="task-head">
        <div>
          <p>DOWNLOAD STATUS</p>
          <h3>{{ status }}</h3>
        </div>
        <span>{{ Math.round(percentage) }}%</span>
      </div>
      <div v-if="running || percentage > 0" class="progress-track" role="progressbar" :aria-valuenow="Math.round(percentage)" aria-valuemin="0" aria-valuemax="100" :aria-label="status">
        <i :style="{ width: `${percentage}%` }"></i>
      </div>
      <p v-if="savingFiles" class="saving-hint">正在写入本机文件，请勿关闭窗口</p>
      <ul v-if="savedFiles.length" class="saved-list">
        <li v-for="file in savedFiles" :key="file.path">
          <span :title="file.path">{{ file.name }}</span>
          <button
            v-if="desktop"
            type="button"
            @click="$emit('reveal-file', file)"
          >
            在文件夹中显示
          </button>
        </li>
      </ul>
      <div class="task-stats">
        <span v-if="urlCount > 1">{{ currentIndex + 1 }} / {{ urlCount }}</span>
        <span>{{ taskTitle || "尚未开始" }}</span>
        <span>{{ speed }}</span>
        <span v-if="eta">ETA {{ eta }}</span>
      </div>
      <div
        v-if="logs.length"
        ref="logView"
        class="log-view"
        aria-live="polite"
      >
        <p
          v-for="(item, index) in logs.slice(-7)"
          :key="`${index}-${item.time}`"
          :class="item.level"
        >
          <time>{{ item.time }}</time>{{ item.line }}
        </p>
      </div>
    </article>

    <section class="command-card" aria-labelledby="command-heading">
      <div class="command-head">
        <h3 id="command-heading">对应命令</h3>
        <button type="button" @click="$emit('copy-command')">复制</button>
      </div>
      <code>{{ command }}</code>
    </section>
  </aside>
</template>
