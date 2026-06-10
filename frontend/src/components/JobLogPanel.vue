<template>
  <ProcessLogPanel
    :logs="logs"
    :loading="loading"
    :polling="polling"
    title="Журнал задачи"
    empty-text="Логи появятся после запуска задачи"
    class="log-panel-wrap"
  />
</template>

<script setup>
import ProcessLogPanel from './ProcessLogPanel.vue';

defineProps({
  logs: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  polling: { type: Boolean, default: false },
});
</script>

<style scoped>
.log-panel-wrap {
  padding: 0;
  border: none;
  background: transparent;
  max-height: 420px;
}
</style>
