<template>
  <div v-if="active" class="inline-task" role="status">
    <div class="inline-track">
      <div class="inline-fill" :style="{ width: `${progress}%` }" />
    </div>
    <span class="inline-label">{{ label }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';

const props = defineProps({
  /** Совпадение context.accountId */
  accountId: { type: Number, default: null },
  /** Совпадение context.username (без @) */
  username: { type: String, default: null },
  /** Текст, если не брать из store */
  fallbackLabel: { type: String, default: 'Выполняется…' },
});

const taskStore = useAsyncTaskStore();

const active = computed(() => {
  if (!taskStore.isActive) return false;
  if (props.accountId != null && taskStore.matchesContext('accountId', props.accountId)) {
    return true;
  }
  if (props.username) {
    const u = props.username.replace(/^@/, '').toLowerCase();
    const ctx = taskStore.active?.context?.username;
    if (ctx && ctx.replace(/^@/, '').toLowerCase() === u) return true;
  }
  return props.accountId == null && props.username == null && taskStore.isActive;
});

const progress = computed(() =>
  taskStore.active?.done ? 100 : taskStore.progressPercent
);

const label = computed(() => {
  if (!active.value) return '';
  return taskStore.currentStep || props.fallbackLabel;
});
</script>

<style scoped>
.inline-task {
  margin-top: 0.45rem;
}

.inline-track {
  height: 3px;
  border-radius: 99px;
  background: rgba(59, 130, 246, 0.2);
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.inline-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), #60a5fa);
  transition: width 0.5s ease;
}

.inline-label {
  font-size: 0.72rem;
  color: #93c5fd;
  display: block;
  line-height: 1.3;
}
</style>
