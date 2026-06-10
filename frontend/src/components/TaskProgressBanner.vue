<template>
  <Transition name="task-banner">
    <div v-if="showBanner" class="task-banner" role="status" aria-live="polite">
      <div class="task-banner-inner">
        <div class="task-icon" :class="`task-icon--${taskStore.active?.icon || 'default'}`" aria-hidden="true">
          <span class="spinner-ring" />
          <span class="icon-glyph">{{ iconGlyph }}</span>
        </div>

        <div class="task-body">
          <div class="task-head">
            <strong class="task-title">{{ bannerTitle }}</strong>
            <span v-if="contextLabel" class="task-context">{{ contextLabel }}</span>
            <span class="task-time">{{ elapsedLabel }}</span>
            <VerboseLogToggle class="task-verbose-toggle" />
          </div>

          <p v-if="taskStore.isActive" class="task-step">{{ taskStore.currentStep }}</p>
          <p v-else-if="uiPrefs.verboseLogs" class="task-step task-step--done">Операция завершена — см. журнал ниже</p>

          <div v-if="taskStore.isActive" class="task-track">
            <div
              class="task-fill"
              :class="{ 'task-fill--done': taskStore.active?.done }"
              :style="{ width: `${displayProgress}%` }"
            />
          </div>

          <p v-if="taskStore.isActive" class="task-hint">
            Связь с Telegram может занять до 2 минут — не закрывайте страницу, пока идёт операция.
          </p>
        </div>
      </div>

      <ProcessLogPanel
        v-if="uiPrefs.verboseLogs && runtimeLogs.length"
        class="task-log-panel"
        :logs="runtimeLogs"
        :polling="taskStore.isActive"
        :show-progress="false"
        :show-toggle="false"
        title="Детальный журнал"
        compact
        :show-clear="!taskStore.isActive"
        @clear="taskStore.clearLastLogs()"
      />
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue';
import ProcessLogPanel from './ProcessLogPanel.vue';
import VerboseLogToggle from './VerboseLogToggle.vue';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { useUiPrefsStore } from '../stores/uiPrefsStore';

const taskStore = useAsyncTaskStore();
const uiPrefs = useUiPrefsStore();

const runtimeLogs = computed(() => taskStore.visibleRuntimeLogs);

const showBanner = computed(
  () => taskStore.isActive || (uiPrefs.verboseLogs && runtimeLogs.value.length > 0)
);

const bannerTitle = computed(
  () => taskStore.active?.title || 'Последняя операция'
);

const contextLabel = computed(() => taskStore.contextLabel);

const displayProgress = computed(() =>
  taskStore.active?.done ? 100 : taskStore.progressPercent
);

const elapsedLabel = computed(() => {
  const s = taskStore.elapsedSec;
  if (!taskStore.isActive && runtimeLogs.value.length) return '';
  if (s < 60) return `${s} с`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, '0')}`;
});

const iconGlyph = computed(() => {
  const icon = taskStore.active?.icon;
  if (icon === 'botfather') return 'BF';
  if (icon === 'telegram') return 'TG';
  return '…';
});
</script>

<style scoped>
.task-banner {
  position: sticky;
  top: 0;
  z-index: 50;
  margin: -1.25rem -1.5rem 1rem;
  padding: 0 1.5rem;
  pointer-events: none;
}

.task-banner-inner {
  pointer-events: auto;
  display: flex;
  gap: 0.85rem;
  padding: 0.85rem 1rem;
  border-radius: var(--radius);
  border: 1px solid rgba(59, 130, 246, 0.45);
  background: linear-gradient(135deg, rgba(30, 58, 95, 0.95), rgba(26, 35, 50, 0.98));
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}

.task-log-panel {
  pointer-events: auto;
  margin-top: 0.5rem;
  max-height: 260px;
}

.task-verbose-toggle {
  margin-left: auto;
}

.task-step--done {
  color: #86efac;
  font-size: 0.78rem;
}

.task-icon {
  position: relative;
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid rgba(59, 130, 246, 0.25);
  border-top-color: var(--accent);
  animation: spin 0.9s linear infinite;
}

.task-icon--botfather .spinner-ring {
  border-top-color: #a78bfa;
}

.icon-glyph {
  position: relative;
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: var(--text);
}

.task-body {
  flex: 1;
  min-width: 0;
}

.task-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem 0.65rem;
  margin-bottom: 0.25rem;
}

.task-title {
  font-size: 0.9rem;
}

.task-context {
  font-size: 0.78rem;
  color: #93c5fd;
}

.task-time {
  margin-left: auto;
  font-size: 0.75rem;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.task-step {
  margin: 0 0 0.45rem;
  font-size: 0.82rem;
  color: #c4d4e8;
  animation: step-fade 0.35s ease;
}

.task-track {
  height: 5px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.task-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), #60a5fa);
  transition: width 0.6s ease;
}

.task-fill--done {
  background: linear-gradient(90deg, var(--success), #4ade80);
  transition: width 0.25s ease;
}

.task-hint {
  margin: 0.35rem 0 0;
  font-size: 0.7rem;
  color: var(--muted);
}

.task-banner-enter-active,
.task-banner-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.task-banner-enter-from,
.task-banner-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes step-fade {
  from {
    opacity: 0.4;
  }
  to {
    opacity: 1;
  }
}
</style>
