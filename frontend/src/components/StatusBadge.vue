<template>
  <span class="badge" :class="`badge--${status}`">{{ label }}</span>
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
  exhausted: 'Лимит',
  error: 'Ошибка',
  active: 'Активен',
  stopped: 'Остановлен',
  available: 'Свободен',
  in_use: 'В кампании',
  disabled: 'Отключён',
};

const label = computed(() => labels[props.status] || props.status);
</script>

<style scoped>
.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.badge--draft,
.badge--pending {
  background: rgba(139, 156, 179, 0.2);
  color: var(--muted);
}

.badge--queued {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
}

.badge--running,
.badge--creating {
  background: rgba(59, 130, 246, 0.25);
  color: #60a5fa;
}

.badge--completed,
.badge--ready,
.badge--active,
.badge--available {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.badge--failed,
.badge--error {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.badge--exhausted,
.badge--stopped,
.badge--cancelled {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}
</style>
