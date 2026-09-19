<script setup>
defineProps({
  health: { type: Object, default: null },
  theme: { type: String, default: "paper" },
});

defineEmits(["toggle-theme"]);
</script>

<template>
  <header class="topbar">
    <a class="brand" href="#main" aria-label="回到下载区">
      <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
      <span>FRAME<span class="brand-accent">/GET</span></span>
    </a>
    <div class="header-actions">
      <button
        class="theme-toggle"
        type="button"
        :aria-label="theme === 'paper' ? '切换到暗色主题' : '切换到亮色主题'"
        @click="$emit('toggle-theme')"
      >
        <span aria-hidden="true">{{ theme === "paper" ? "◐" : "◑" }}</span>
        {{ theme === "paper" ? "朋克主题" : "纸张主题" }}
      </button>
      <div class="service-state" :class="{ offline: !health?.ok }">
        <span class="status-dot"></span>
        {{ health?.ok ? `引擎在线 · ${health.version}` : "后端未连接" }}
      </div>
    </div>
  </header>
</template>
