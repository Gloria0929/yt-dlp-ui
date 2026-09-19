<script setup>
import { nextTick, ref, watch } from "vue";

const props = defineProps({
  info: { type: Object, default: null },
  infoLoading: { type: Boolean, default: false },
  videoMeta: { type: Array, default: () => [] },
  running: { type: Boolean, default: false },
  percentage: { type: Number, default: 0 },
  status: { type: String, default: "" },
  urlCount: { type: Number, default: 0 },
  currentIndex: { type: Number, default: 0 },
  taskTitle: { type: String, default: "" },
  speed: { type: String, default: "" },
  eta: { type: String, default: "" },
  logs: { type: Array, default: () => [] },
  command: { type: String, default: "" },
});

defineEmits(["copy-command"]);

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

    <article v-else class="empty-preview">
      <div class="preview-art" aria-hidden="true"><span>▶</span></div>
      <p>视频预览</p>
      <h3>
        {{
          infoLoading
            ? "正在连接视频站点…"
            : "读取后会在这里显示标题与封面"
        }}
      </h3>
    </article>

    <article
      class="task-card"
      :class="{ active: running, complete: !running && percentage === 100 }"
    >
      <div class="task-head">
        <div>
          <p>DOWNLOAD STATUS</p>
          <h3>{{ status }}</h3>
        </div>
        <span>{{ Math.round(percentage) }}%</span>
      </div>
      <div class="progress-track">
        <i :style="{ width: `${percentage}%` }"></i>
      </div>
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
