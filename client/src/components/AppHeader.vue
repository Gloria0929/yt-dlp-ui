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
        <span class="theme-icon" aria-hidden="true">
          <svg v-if="theme === 'paper'" viewBox="0 0 24 24" focusable="false">
            <path d="M20 15.4A8.5 8.5 0 0 1 8.6 4a8.5 8.5 0 1 0 11.4 11.4Z" />
          </svg>
          <svg v-else viewBox="0 0 24 24" focusable="false">
            <circle cx="12" cy="12" r="3.5" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
          </svg>
        </span>
        <span class="theme-label">{{ theme === "paper" ? "朋克主题" : "纸张主题" }}</span>
      </button>
      <div class="service-state" :class="{ offline: !health?.ok }">
        <span class="status-dot"></span>
        {{ health?.ok ? `引擎在线 · ${health.version}` : "后端未连接" }}
      </div>
    </div>
  </header>
</template>
