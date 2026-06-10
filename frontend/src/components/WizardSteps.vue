<template>
  <div class="wizard-steps" role="list" :aria-label="ariaLabel">
    <button
      v-for="(step, i) in steps"
      :key="step.id || i"
      type="button"
      class="wizard-step"
      role="listitem"
      :class="{
        active: current >= i + 1,
        done: current > i + 1,
        clickable: clickable && current > i + 1,
      }"
      :disabled="!clickable || current <= i + 1"
      @click="clickable && current > i + 1 ? $emit('go', i + 1) : null"
    >
      <span class="wizard-step-num">{{ i + 1 }}</span>
      <span class="wizard-step-label">{{ step.label }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  steps: { type: Array, required: true },
  current: { type: Number, default: 1 },
  clickable: { type: Boolean, default: false },
  ariaLabel: { type: String, default: 'Шаги' },
});

defineEmits(['go']);
</script>

<style scoped>
.wizard-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.wizard-step {
  flex: 1;
  min-width: 6rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.45rem 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 0.72rem;
  cursor: default;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}

.wizard-step.clickable:not(:disabled) {
  cursor: pointer;
}

.wizard-step.clickable:not(:disabled):hover {
  border-color: var(--accent);
  background: rgba(59, 130, 246, 0.08);
}

.wizard-step.active {
  border-color: var(--accent);
  color: var(--text);
  background: rgba(59, 130, 246, 0.1);
}

.wizard-step.done {
  color: #86efac;
  border-color: rgba(34, 197, 94, 0.35);
}

.wizard-step-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 50%;
  font-size: 0.68rem;
  font-weight: 700;
  background: rgba(139, 156, 179, 0.15);
}

.wizard-step.active .wizard-step-num {
  background: rgba(59, 130, 246, 0.25);
  color: #93c5fd;
}

.wizard-step.done .wizard-step-num {
  background: rgba(34, 197, 94, 0.2);
  color: #86efac;
}

.wizard-step-label {
  text-align: center;
  line-height: 1.25;
}
</style>
