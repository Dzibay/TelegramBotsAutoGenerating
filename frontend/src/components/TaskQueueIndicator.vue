<template>
  <RouterLink v-if="store.hasActive" :to="{ name: 'task-queue' }" class="queue-indicator">
    <span class="pulse" />
    <span>{{ label }}</span>
  </RouterLink>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue';
import { RouterLink } from 'vue-router';
import { useTaskQueueStore } from '../stores/taskQueueStore';

const store = useTaskQueueStore();

const label = computed(() => {
  const n = store.activeCount || store.activeTasks.length;
  return n === 1 ? '1 задача в очереди' : `${n} задач в очереди`;
});

onMounted(() => store.startPolling());
onUnmounted(() => {
  if (window.location.pathname !== '/app/tasks') {
    store.stopPolling();
  }
});
</script>

<style scoped>
.queue-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid rgba(59, 130, 246, 0.28);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: #bfdbfe;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 600;
}

.queue-indicator:hover {
  color: #fff;
  text-decoration: none;
  border-color: rgba(59, 130, 246, 0.5);
}

.pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.18);
}
</style>
