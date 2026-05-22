<template>
  <div class="workspace-tabs" role="tablist">
    <button
      v-for="t in tabs"
      :key="t.id"
      type="button"
      role="tab"
      class="ws-tab"
      :class="{ active: modelValue === t.id }"
      :aria-selected="modelValue === t.id"
      @click="$emit('update:modelValue', t.id)"
    >
      {{ t.label }}
      <span v-if="t.badge != null" class="ws-badge">{{ t.badge }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, required: true },
  tabs: { type: Array, required: true },
});

defineEmits(['update:modelValue']);
</script>

<style scoped>
.workspace-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 1rem;
  padding: 0.35rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.ws-tab {
  flex: 1;
  min-width: 7rem;
  padding: 0.55rem 0.85rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
}

.ws-tab:hover {
  color: var(--text);
  background: var(--surface-hover);
}

.ws-tab.active {
  background: var(--accent);
  color: #fff;
}

.ws-badge {
  margin-left: 0.35rem;
  padding: 0.05rem 0.4rem;
  border-radius: 99px;
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.2);
}

.ws-tab.active .ws-badge {
  background: rgba(0, 0, 0, 0.2);
}
</style>
