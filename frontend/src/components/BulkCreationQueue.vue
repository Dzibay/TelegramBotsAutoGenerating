<template>
  <div class="queue-panel">
    <div v-if="active" class="queue-progress">
      <div class="queue-track" role="progressbar" :aria-valuenow="doneCount" :aria-valuemax="totalCount">
        <div class="queue-fill" :style="{ width: `${progressPercent}%` }" />
      </div>
      <p class="queue-summary">
        <template v-if="jobTotal > 0">
          {{ jobDone }} из {{ jobTotal }} обработано
          <span v-if="jobCreated != null"> · создано: {{ jobCreated }}</span>
        </template>
        <template v-else>
          {{ doneCount }} из {{ totalCount }} завершено
          <span v-if="failedCount"> · ошибок: {{ failedCount }}</span>
        </template>
        <span v-if="floodWaitRemaining > 0" class="flood-wait">
          · пауза Telegram: {{ floodWaitLabel }}
        </span>
        <span v-else-if="jobMessage" class="job-msg"> · {{ jobMessage }}</span>
        <span v-else-if="currentLabel"> · сейчас: {{ currentLabel }}</span>
      </p>
      <InlineTaskIndicator v-if="creating" :username="currentUsername" fallback-label="Создаём бота в Telegram…" />
    </div>

    <div class="queue-columns">
      <section class="queue-list card-inner">
        <h4>
          Очередь
          <span v-if="creating" class="live-dot" title="Создание идёт">●</span>
        </h4>
        <ul class="status-list">
          <li
            v-for="(item, i) in items"
            :key="item.id"
            class="status-item"
            :class="`status-item--${item.queueStatus}`"
          >
            <span class="status-icon">{{ statusIcon(item.queueStatus) }}</span>
            <span class="status-num">{{ i + 1 }}.</span>
            <span class="status-name">
              {{ item.displayName?.trim() || '—' }}
              <span v-if="item.username" class="status-user">@{{ item.username.replace(/^@/, '') }}</span>
            </span>
            <span class="status-label">{{ statusLabel(item.queueStatus) }}</span>
          </li>
        </ul>
      </section>

      <ProcessLogPanel
        class="queue-logs-panel"
        :logs="logs"
        :polling="creating"
        title="Журнал"
        empty-text="Записи появятся после старта"
        compact
        :show-progress="false"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import InlineTaskIndicator from './InlineTaskIndicator.vue';
import ProcessLogPanel from './ProcessLogPanel.vue';
import { formatWaitLabel } from '../utils/floodWait';

const props = defineProps({
  items: { type: Array, default: () => [] },
  logs: { type: Array, default: () => [] },
  creating: { type: Boolean, default: false },
  active: { type: Boolean, default: false },
  currentUsername: { type: String, default: '' },
  currentLabel: { type: String, default: '' },
  floodWaitRemaining: { type: Number, default: 0 },
  jobDone: { type: Number, default: 0 },
  jobTotal: { type: Number, default: 0 },
  jobCreated: { type: Number, default: null },
  jobMessage: { type: String, default: '' },
});

const totalCount = computed(() => props.items.filter((i) => i.username?.trim()).length);

const doneCount = computed(
  () => props.items.filter((i) => i.queueStatus === 'done' || i.queueStatus === 'error').length
);

const failedCount = computed(() => props.items.filter((i) => i.queueStatus === 'error').length);

const progressPercent = computed(() => {
  if (props.jobTotal > 0) {
    return Math.round((props.jobDone / props.jobTotal) * 100);
  }
  if (!totalCount.value) return 0;
  return Math.round((doneCount.value / totalCount.value) * 100);
});

const floodWaitLabel = computed(() => formatWaitLabel(props.floodWaitRemaining));

function statusIcon(status) {
  const map = {
    pending: '○',
    creating: '●',
    waiting: '◷',
    done: '✓',
    error: '✗',
    skipped: '—',
  };
  return map[status] || '○';
}

function statusLabel(status) {
  if (status === 'waiting' && props.floodWaitRemaining > 0) {
    return `Пауза ${floodWaitLabel.value}`;
  }
  const map = {
    pending: 'Ожидает',
    creating: 'Создаётся',
    waiting: 'Пауза Telegram',
    done: 'Создан',
    error: 'Ошибка',
    skipped: 'Пропущен',
  };
  return map[status] || status;
}
</script>

<style scoped>
.queue-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.queue-progress {
  padding: 0.9rem 1rem;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(37, 99, 235, 0.04));
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: var(--radius-sm);
}

.queue-track {
  height: 6px;
  border-radius: 99px;
  background: rgba(59, 130, 246, 0.15);
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.queue-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), #60a5fa);
  transition: width 0.4s ease;
}

.queue-summary {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text);
}

.flood-wait {
  color: #facc15;
}

.job-msg {
  color: #93c5fd;
}

.queue-columns {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 1rem;
  align-items: stretch;
}

.queue-logs-panel {
  min-height: 280px;
}

@media (max-width: 800px) {
  .queue-columns {
    grid-template-columns: 1fr;
  }
}

.card-inner h4 {
  margin: 0 0 0.65rem;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.live-dot {
  font-size: 0.7rem;
  color: #4ade80;
  animation: pulse 1.5s infinite;
}

.status-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 280px;
  overflow-y: auto;
}

.status-item {
  display: grid;
  grid-template-columns: 1.2rem 1.5rem 1fr auto;
  gap: 0.35rem;
  align-items: center;
  padding: 0.35rem 0;
  border-bottom: 1px solid rgba(45, 58, 77, 0.35);
  font-size: 0.82rem;
}

.status-icon {
  text-align: center;
}

.status-num {
  color: var(--muted);
  font-size: 0.75rem;
}

.status-user {
  color: var(--muted);
  margin-left: 0.25rem;
}

.status-label {
  font-size: 0.72rem;
  color: var(--muted);
  white-space: nowrap;
}

.status-item--creating .status-label,
.status-item--creating .status-icon {
  color: #60a5fa;
}

.status-item--waiting .status-label,
.status-item--waiting .status-icon {
  color: #facc15;
}

.status-item--done .status-label,
.status-item--done .status-icon {
  color: #4ade80;
}

.status-item--error .status-label,
.status-item--error .status-icon {
  color: #f87171;
}

@keyframes pulse {
  50% {
    opacity: 0.4;
  }
}
</style>
