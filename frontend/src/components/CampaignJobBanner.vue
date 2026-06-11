<template>
  <section v-if="job && active" class="job-banner card">
    <div class="job-banner-head">
      <div>
        <h3>Фоновая задача #{{ job.id }}</h3>
        <p class="job-banner-meta">
          <StatusBadge :status="job.status" />
          <span v-if="job.total_accounts">
            {{ job.processed_accounts ?? 0 }}/{{ job.total_accounts }} обработано
          </span>
          <span v-if="job.total_bots_created != null"> · создано: {{ job.total_bots_created }}</span>
          <span v-if="etaLabel" class="job-eta"> · {{ etaLabel }}</span>
        </p>
        <p v-if="job.progress_message" class="job-msg">{{ job.progress_message }}</p>
      </div>
      <div class="job-banner-actions">
        <RouterLink
          v-if="bulkLink"
          :to="bulkLink"
          class="btn btn-sm btn-ghost"
        >
          Открыть очередь
        </RouterLink>
        <button
          type="button"
          class="btn btn-sm btn-ghost danger"
          :disabled="cancelling"
          @click="$emit('cancel')"
        >
          {{ cancelling ? 'Останавливаем…' : 'Остановить' }}
        </button>
      </div>
    </div>

    <div v-if="job.total_accounts" class="job-track" role="progressbar" :aria-valuenow="progressPercent">
      <div class="job-fill" :style="{ width: `${progressPercent}%` }" />
    </div>

    <JobLogPanel :logs="logs" :loading="logsLoading" :polling="active" />
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import JobLogPanel from './JobLogPanel.vue';
import StatusBadge from './StatusBadge.vue';
import { useSettingsStore } from '../stores/settingsStore';
import { estimateBulkCreationSec, formatEtaRemaining } from '../utils/estimateJobTime';

const props = defineProps({
  job: { type: Object, default: null },
  logs: { type: Array, default: () => [] },
  logsLoading: { type: Boolean, default: false },
  active: { type: Boolean, default: false },
  cancelling: { type: Boolean, default: false },
  bulkLink: { type: Object, default: null },
  elapsedSec: { type: Number, default: 0 },
});

defineEmits(['cancel']);

const settingsStore = useSettingsStore();

const progressPercent = computed(() => {
  if (!props.job?.total_accounts) return 0;
  return Math.min(
    100,
    Math.round(((props.job.processed_accounts ?? 0) / props.job.total_accounts) * 100)
  );
});

const etaLabel = computed(() => {
  if (!props.active || !props.job?.total_accounts) return '';
  const est = estimateBulkCreationSec(props.job.total_accounts, settingsStore.botfatherPacing);
  return formatEtaRemaining(props.elapsedSec, est);
});
</script>

<style scoped>
.job-banner {
  margin-bottom: 1.25rem;
  padding: 1.15rem 1.25rem;
  border-color: rgba(59, 130, 246, 0.3);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.05));
}

.job-banner-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.job-banner-head h3 {
  margin: 0 0 0.35rem;
  font-size: 0.95rem;
}

.job-banner-meta {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
  font-size: 0.82rem;
  color: var(--muted);
}

.job-msg {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
  color: #93c5fd;
}

.job-eta {
  color: #facc15;
}

.job-banner-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: flex-start;
}

.job-track {
  height: 5px;
  border-radius: 99px;
  background: rgba(59, 130, 246, 0.15);
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.job-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), #60a5fa);
  transition: width 0.4s ease;
}
</style>
