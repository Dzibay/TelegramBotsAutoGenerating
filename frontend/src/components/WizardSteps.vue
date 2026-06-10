<template>
  <div class="wizard-steps" role="list" :aria-label="ariaLabel">
    <div
      v-for="(step, i) in steps"
      :key="step.id || i"
      class="wizard-step-wrap"
      :class="{ 'wizard-step-wrap--last': i === steps.length - 1 }"
    >
      <button
        type="button"
        class="wizard-step"
        role="listitem"
        :class="{
          active: current === i + 1,
          done: current > i + 1,
          clickable: clickable && current > i + 1,
        }"
        :disabled="!clickable || current <= i + 1"
        @click="clickable && current > i + 1 ? $emit('go', i + 1) : null"
      >
        <span class="wizard-step-num">
          <Check v-if="current > i + 1" :size="12" />
          <template v-else>{{ i + 1 }}</template>
        </span>
        <span class="wizard-step-label">{{ step.label }}</span>
      </button>
      <div v-if="i < steps.length - 1" class="wizard-connector" :class="{ done: current > i + 1 }" />
    </div>
  </div>
</template>

<script setup>
import { Check } from 'lucide-vue-next';

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
  align-items: flex-start;
  gap: 0;
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  backdrop-filter: var(--glass);
}

.wizard-step-wrap {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.wizard-step-wrap--last {
  flex: 0 0 auto;
}

.wizard-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 0.72rem;
  font-weight: 500;
  cursor: default;
  transition: color 0.15s;
  flex-shrink: 0;
}

.wizard-step.clickable:not(:disabled) {
  cursor: pointer;
}

.wizard-step.clickable:not(:disabled):hover .wizard-step-num {
  border-color: var(--accent);
}

.wizard-step.active {
  color: var(--text);
}

.wizard-step.done {
  color: #4ade80;
}

.wizard-step-num {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  font-size: 0.72rem;
  font-weight: 700;
  border: 2px solid rgba(139, 156, 179, 0.25);
  background: rgba(8, 12, 20, 0.6);
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}

.wizard-step.active .wizard-step-num {
  border-color: var(--accent);
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
}

.wizard-step.done .wizard-step-num {
  border-color: rgba(34, 197, 94, 0.5);
  background: var(--success-soft);
  color: #4ade80;
}

.wizard-step-label {
  text-align: center;
  line-height: 1.25;
  max-width: 5.5rem;
}

.wizard-connector {
  flex: 1;
  height: 2px;
  margin: 0 0.35rem;
  margin-bottom: 1.1rem;
  background: rgba(139, 156, 179, 0.15);
  border-radius: 99px;
  transition: background 0.2s;
}

.wizard-connector.done {
  background: rgba(34, 197, 94, 0.4);
}

@media (max-width: 640px) {
  .wizard-steps {
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .wizard-step-wrap {
    flex: 0 0 calc(50% - 0.25rem);
  }

  .wizard-connector {
    display: none;
  }
}
</style>
