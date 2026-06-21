<template>
  <div v-if="message || status" class="operation-status">
    <p v-if="message" class="operation-status__message">{{ message }}</p>
    <p v-if="statusLabel" class="operation-status__meta">{{ statusLabel }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  message: { type: String, default: '' },
  status: { type: String, default: '' },
});

const STATUS_MAP = {
  queued: 'В очереди',
  running: 'Выполняется',
  completed: 'Готово',
  failed: 'Ошибка',
  cancelled: 'Отменено',
};

const statusLabel = computed(() => STATUS_MAP[props.status] || props.status || '');
</script>

<style scoped>
.operation-status {
  margin: 0.75rem 0;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: var(--surface-muted, rgba(0, 0, 0, 0.04));
}
.operation-status__message {
  margin: 0;
  font-weight: 500;
}
.operation-status__meta {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  opacity: 0.75;
}
</style>
