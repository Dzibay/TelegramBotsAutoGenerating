<template>
  <div class="empty-state" :class="{ compact }">
    <div v-if="icon" class="empty-icon" aria-hidden="true">{{ icon }}</div>
    <p v-if="title" class="empty-title">{{ title }}</p>
    <p v-if="description" class="empty-desc muted">{{ description }}</p>
    <div v-if="$slots.default" class="empty-actions">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: '' },
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  compact: { type: Boolean, default: false },
});
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 2rem 1.25rem;
}

.empty-state.compact {
  padding: 1.25rem 0.75rem;
}

.empty-icon {
  font-size: 2rem;
  line-height: 1;
  margin-bottom: 0.65rem;
  opacity: 0.85;
}

.empty-title {
  margin: 0 0 0.35rem;
  font-size: 1rem;
  font-weight: 600;
}

.empty-desc {
  margin: 0 auto;
  max-width: 28rem;
  font-size: 0.88rem;
  line-height: 1.5;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 1rem;
}
</style>
