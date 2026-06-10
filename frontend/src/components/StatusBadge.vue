<template>
  <span class="badge" :class="`badge--${status}`">
    <span v-if="isActive" class="badge-dot" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  status: { type: String, required: true },
});

const labels = {
  draft: 'Черновик',
  queued: 'В очереди',
  running: 'Выполняется',
  completed: 'Готово',
  failed: 'Ошибка',
  cancelled: 'Отменено',
  pending: 'Ожидание',
  ready: 'Готов',
  creating: 'Создание',
  exhausted: 'Лимит ботов',
  error: 'Ошибка',
  active: 'Активен',
  stopped: 'Остановлен',
  available: 'Свободен',
  in_use: 'В кампании',
  disabled: 'Отключён',
};

const label = computed(() => labels[props.status] || props.status);

const isActive = computed(() =>
  ['active', 'completed', 'ready', 'available', 'running', 'creating'].includes(props.status)
);
</script>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  border: 1px solid transparent;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.badge--draft,
.badge--pending {
  background: rgba(139, 156, 179, 0.12);
  border-color: rgba(139, 156, 179, 0.2);
  color: var(--muted);
}

.badge--queued {
  background: rgba(59, 130, 246, 0.12);
  border-color: rgba(59, 130, 246, 0.25);
  color: #93c5fd;
}

.badge--running,
.badge--creating {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.badge--completed,
.badge--ready,
.badge--active,
.badge--available {
  background: var(--success-soft);
  border-color: rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

.badge--failed,
.badge--error {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.badge--exhausted,
.badge--stopped,
.badge--cancelled {
  background: var(--warning-soft);
  border-color: rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.badge--in_use {
  background: rgba(139, 92, 246, 0.12);
  border-color: rgba(139, 92, 246, 0.3);
  color: #c4b5fd;
}
</style>
