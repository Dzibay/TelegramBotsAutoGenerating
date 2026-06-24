<template>
  <div class="process-log" :class="{ 'process-log--compact': compact }">
    <header class="process-log-header">
      <div class="process-log-title-wrap">
        <h3 v-if="title">{{ title }}</h3>
        <span v-if="polling" class="live-dot" title="Обновляется">● live</span>
        <span v-if="hiddenDebugCount" class="log-filter-hint" :title="filterHintTitle">
          +{{ hiddenDebugCount }} debug
        </span>
      </div>
      <div class="process-log-actions">
        <VerboseLogToggle v-if="showToggle" />
        <button
          v-if="logs.length && showClear"
          type="button"
          class="btn-ghost btn-xs log-clear-btn"
          @click="$emit('clear')"
        >
          Очистить
        </button>
      </div>
    </header>

    <div v-if="polling && showProgress" class="process-log-progress">
      <div class="process-log-progress-fill" />
    </div>

    <p v-if="!logs.length && !loading" class="muted empty">{{ emptyText }}</p>
    <p v-else-if="loading && !logs.length" class="muted empty">Загрузка…</p>
    <p v-else-if="!displayLogs.length && logs.length" class="muted empty">
      Включите «Детальные логи», чтобы увидеть {{ hiddenDebugCount }} служебных записей
    </p>

    <div ref="scrollRef" class="process-log-body">
      <div
        v-for="entry in displayLogs"
        :key="entry.id"
        class="log-row"
        :class="[
          `log-row--${entry.level}`,
          { 'log-row--break': entry._rowBreak },
        ]"
      >
        <div class="log-row-main">
          <time>{{ formatLogTime(entry.time) }}</time>
          <span v-if="uiPrefs.verboseLogs" class="log-level">{{ levelLabel(entry.level) }}</span>
          <span v-if="uiPrefs.verboseLogs && entry.source === 'client'" class="log-src">CLI</span>
          <span
            v-for="(tag, idx) in extractLogTags(entry.context)"
            :key="`${entry.id}-tag-${idx}`"
            class="log-tag"
            :class="`log-tag--${tag.kind}`"
          >{{ tag.text }}</span>
          <span class="log-msg">{{ enrichLogMessage(entry) }}</span>
        </div>
        <details
          v-if="uiPrefs.verboseLogs && entry.context && hasExtraContext(entry.context)"
          class="log-context"
        >
          <summary>техн. детали</summary>
          <pre>{{ formatContext(entry.context) }}</pre>
        </details>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import VerboseLogToggle from './VerboseLogToggle.vue';
import {
  enrichLogMessage,
  extractLogTags,
  filterLogsForMode,
  formatContext,
  formatLogTime,
  hasExtraContext,
  levelLabel,
  normalizeLogList,
  withLogRowBreaks,
} from '../utils/formatLogEntry';
import { useUiPrefsStore } from '../stores/uiPrefsStore';

const props = defineProps({
  logs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  polling: { type: Boolean, default: false },
  title: { type: String, default: 'Журнал' },
  emptyText: { type: String, default: 'Записи появятся при выполнении операции' },
  showToggle: { type: Boolean, default: true },
  showClear: { type: Boolean, default: false },
  showProgress: { type: Boolean, default: true },
  compact: { type: Boolean, default: false },
});

defineEmits(['clear']);

const uiPrefs = useUiPrefsStore();
const scrollRef = ref(null);

const normalized = computed(() => normalizeLogList(props.logs));
const hiddenDebugCount = computed(
  () => normalized.value.filter((e) => e.level === 'debug').length
);
const displayLogs = computed(() =>
  withLogRowBreaks(filterLogsForMode(normalized.value, uiPrefs.verboseLogs))
);

const filterHintTitle = computed(() =>
  uiPrefs.verboseLogs
    ? ''
    : 'Служебные debug-записи скрыты. Включите «Детальные логи».'
);

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
.process-log {
  display: flex;
  flex-direction: column;
  min-height: 240px;
  max-height: 480px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  backdrop-filter: var(--glass);
}

.process-log--compact {
  min-height: 200px;
  max-height: 320px;
  background: rgba(8, 12, 20, 0.5);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.process-log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}

.process-log-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.process-log-header h3 {
  margin: 0;
  font-size: 0.9rem;
}

.process-log-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.log-clear-btn {
  padding: 0.2rem 0.45rem;
  font-size: 0.68rem;
}

.live-dot {
  font-size: 0.68rem;
  color: #4ade80;
  animation: pulse 1.5s infinite;
}

.log-filter-hint {
  font-size: 0.68rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.process-log-progress {
  padding: 0.4rem 0.85rem 0.55rem;
  border-bottom: 1px solid var(--border);
}

.process-log-progress-fill {
  height: 3px;
  border-radius: 99px;
  background: linear-gradient(
    90deg,
    rgba(59, 130, 246, 0.15) 0%,
    var(--accent) 50%,
    rgba(59, 130, 246, 0.15) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.empty {
  padding: 0.85rem;
  text-align: center;
  font-size: 0.82rem;
}

.process-log-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.55rem 0.75rem;
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: 0.76rem;
}

.log-row {
  padding: 0.3rem 0;
  border-bottom: 1px solid rgba(45, 58, 77, 0.35);
}

.log-row--break {
  margin-top: 0.35rem;
  padding-top: 0.55rem;
  border-top: 1px dashed rgba(59, 130, 246, 0.35);
}

.log-row-main {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem 0.45rem;
  align-items: baseline;
}

.log-row time {
  flex-shrink: 0;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.log-level {
  flex-shrink: 0;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--muted);
  opacity: 0.85;
}

.log-src {
  flex-shrink: 0;
  font-size: 0.6rem;
  padding: 0.05rem 0.25rem;
  border-radius: 3px;
  background: rgba(59, 130, 246, 0.15);
  color: #93c5fd;
}

.log-tag {
  flex-shrink: 0;
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0.06rem 0.35rem;
  border-radius: 4px;
  line-height: 1.35;
  font-family: inherit;
}

.log-tag--user {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
}

.log-tag--step {
  background: rgba(167, 139, 250, 0.2);
  color: #c4b5fd;
}

.log-tag--status {
  background: rgba(74, 222, 128, 0.15);
  color: #86efac;
}

.log-row--error .log-tag--status {
  background: rgba(248, 113, 113, 0.15);
  color: #fca5a5;
}

.log-tag--row,
.log-tag--index {
  background: rgba(250, 204, 21, 0.12);
  color: #fde047;
}

.log-tag--account,
.log-tag--bot {
  background: rgba(148, 163, 184, 0.15);
  color: #cbd5e1;
}

.log-tag--wait {
  background: rgba(251, 146, 60, 0.15);
  color: #fdba74;
}

.log-tag--meta {
  background: rgba(100, 116, 139, 0.2);
  color: #94a3b8;
}

.log-msg {
  flex: 1;
  min-width: 8rem;
  word-break: break-word;
}

.log-row--error .log-msg {
  color: #f87171;
}

.log-row--warn .log-msg {
  color: #facc15;
}

.log-row--success .log-msg {
  color: #4ade80;
}

.log-row--debug .log-msg {
  color: var(--muted);
}

.log-context {
  margin: 0.25rem 0 0 3.5rem;
  font-size: 0.7rem;
}

.log-context summary {
  cursor: pointer;
  color: var(--muted);
  user-select: none;
}

.log-context pre {
  margin: 0.35rem 0 0;
  padding: 0.45rem 0.55rem;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(45, 58, 77, 0.5);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: #a8b8cc;
}

@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@keyframes pulse {
  50% {
    opacity: 0.4;
  }
}
</style>
