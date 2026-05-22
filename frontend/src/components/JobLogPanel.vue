<template>
  <div class="log-panel card">
    <header class="log-header">
      <h3>Журнал задачи</h3>
      <span v-if="polling" class="live-dot" title="Обновляется автоматически">● идёт</span>
    </header>

    <div v-if="polling" class="job-progress" role="progressbar" aria-valuetext="Задача выполняется">
      <div class="job-progress-fill" />
      <span class="job-progress-label">Идёт массовое создание ботов — подробности в записях ниже</span>
    </div>

    <p v-if="!logs.length && !loading" class="muted empty">Логи появятся после запуска задачи</p>
    <p v-else-if="loading && !logs.length" class="muted empty">Загрузка…</p>

    <div ref="scrollRef" class="log-body">
      <div
        v-for="entry in logs"
        :key="entry.id"
        class="log-line"
        :class="`log-line--${entry.level}`"
      >
        <time>{{ formatTime(entry.created_at) }}</time>
        <span class="log-msg">{{ entry.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onUnmounted, ref, watch } from 'vue';

const props = defineProps({
  logs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  polling: { type: Boolean, default: false },
});

const scrollRef = ref(null);

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

watch(
  () => props.logs.length,
  async () => {
    await nextTick();
    const el = scrollRef.value;
    if (el) el.scrollTop = el.scrollHeight;
  }
);
</script>

<style scoped>
.log-panel {
  display: flex;
  flex-direction: column;
  min-height: 280px;
  max-height: 420px;
  padding: 0;
  overflow: hidden;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border);
}

.log-header h3 {
  margin: 0;
  font-size: 0.95rem;
}

.live-dot {
  font-size: 0.75rem;
  color: #4ade80;
  animation: pulse 1.5s infinite;
}

.job-progress {
  padding: 0.5rem 1rem 0.65rem;
  border-bottom: 1px solid var(--border);
}

.job-progress-fill {
  height: 4px;
  border-radius: 99px;
  background: linear-gradient(
    90deg,
    rgba(59, 130, 246, 0.2) 0%,
    var(--accent) 50%,
    rgba(59, 130, 246, 0.2) 100%
  );
  background-size: 200% 100%;
  animation: job-shimmer 1.4s ease-in-out infinite;
  margin-bottom: 0.35rem;
}

.job-progress-label {
  font-size: 0.72rem;
  color: #93c5fd;
}

@keyframes job-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@keyframes pulse {
  50% { opacity: 0.4; }
}

.empty {
  padding: 1rem;
  text-align: center;
}

.log-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 1rem;
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 0.8rem;
}

.log-line {
  display: flex;
  gap: 0.65rem;
  padding: 0.25rem 0;
  border-bottom: 1px solid rgba(45, 58, 77, 0.4);
}

.log-line time {
  flex-shrink: 0;
  color: var(--muted);
}

.log-msg {
  word-break: break-word;
}

.log-line--error .log-msg { color: #f87171; }
.log-line--warn .log-msg { color: #facc15; }
.log-line--info .log-msg { color: var(--text); }
.log-line--debug .log-msg { color: var(--muted); }
</style>
