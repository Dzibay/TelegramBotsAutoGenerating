<template>
  <label class="verbose-toggle" :class="{ 'verbose-toggle--on': uiPrefs.verboseLogs }" :title="title">
    <input
      type="checkbox"
      class="verbose-toggle-input"
      :checked="uiPrefs.verboseLogs"
      @change="uiPrefs.setVerboseLogs($event.target.checked)"
    />
    <span class="verbose-toggle-track" aria-hidden="true">
      <span class="verbose-toggle-thumb" />
    </span>
    <span class="verbose-toggle-label">{{ label }}</span>
  </label>
</template>

<script setup>
import { useUiPrefsStore } from '../stores/uiPrefsStore';

defineProps({
  label: { type: String, default: 'Детальные логи' },
  title: {
    type: String,
    default: 'Добавляет debug-записи, уровни логов и технический JSON-контекст',
  },
});

const uiPrefs = useUiPrefsStore();
</script>

<style scoped>
.verbose-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  cursor: pointer;
  user-select: none;
  font-size: 0.75rem;
  color: var(--muted);
  transition: color 0.15s;
}

.verbose-toggle--on {
  color: #93c5fd;
}

.verbose-toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.verbose-toggle-track {
  position: relative;
  width: 2rem;
  height: 1.1rem;
  border-radius: 99px;
  background: rgba(139, 156, 179, 0.25);
  border: 1px solid var(--border);
  transition: background 0.2s, border-color 0.2s;
  flex-shrink: 0;
}

.verbose-toggle--on .verbose-toggle-track {
  background: rgba(59, 130, 246, 0.35);
  border-color: rgba(59, 130, 246, 0.55);
}

.verbose-toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: calc(1.1rem - 6px);
  height: calc(1.1rem - 6px);
  border-radius: 50%;
  background: var(--muted);
  transition: transform 0.2s, background 0.2s;
}

.verbose-toggle--on .verbose-toggle-thumb {
  transform: translateX(0.85rem);
  background: var(--accent);
}

.verbose-toggle-label {
  white-space: nowrap;
}
</style>
