<template>
  <div
    v-if="visible"
    class="telegram-sync-banner card"
    :class="`telegram-sync-banner--${status}`"
  >
    <div class="banner-row">
      <StatusBadge :status="badgeStatus" />
      <p class="banner-text">{{ message }}</p>
    </div>
    <p v-if="errorText" class="banner-error">{{ errorText }}</p>
    <p v-if="syncedAtLabel" class="banner-meta muted">{{ syncedAtLabel }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import StatusBadge from './StatusBadge.vue';

const props = defineProps({
  status: { type: String, default: 'idle' },
  error: { type: String, default: '' },
  syncedAt: { type: String, default: '' },
});

const visible = computed(() =>
  ['pending', 'syncing', 'synced', 'failed'].includes(props.status)
);

const badgeStatus = computed(() => {
  if (props.status === 'syncing') return 'running';
  if (props.status === 'pending') return 'queued';
  if (props.status === 'synced') return 'completed';
  if (props.status === 'failed') return 'failed';
  return props.status;
});

const message = computed(() => {
  switch (props.status) {
    case 'pending':
      return 'Изменения сохранены. Ожидает отправки профиля в Telegram…';
    case 'syncing':
      return 'Обновление имени, описания и аватара в Telegram…';
    case 'synced':
      return 'Профиль в Telegram успешно обновлён.';
    case 'failed':
      return 'Не удалось обновить профиль в Telegram.';
    default:
      return '';
  }
});

const errorText = computed(() =>
  props.status === 'failed' && props.error ? props.error : ''
);

const syncedAtLabel = computed(() => {
  if (props.status !== 'synced' || !props.syncedAt) return '';
  try {
    const dt = new Date(props.syncedAt);
    if (Number.isNaN(dt.getTime())) return '';
    return `Последняя синхронизация: ${dt.toLocaleString('ru-RU')}`;
  } catch {
    return '';
  }
});
</script>

<style scoped>
.telegram-sync-banner {
  margin-bottom: 1rem;
  padding: 0.85rem 1rem;
}

.banner-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.65rem;
}

.banner-text {
  margin: 0;
  font-size: 0.92rem;
}

.banner-error {
  margin: 0.55rem 0 0;
  color: #f87171;
  font-size: 0.88rem;
}

.banner-meta {
  margin: 0.45rem 0 0;
  font-size: 0.8rem;
}

.telegram-sync-banner--pending,
.telegram-sync-banner--syncing {
  border-color: rgba(59, 130, 246, 0.25);
  background: rgba(59, 130, 246, 0.08);
}

.telegram-sync-banner--synced {
  border-color: rgba(34, 197, 94, 0.25);
  background: var(--success-soft, rgba(34, 197, 94, 0.08));
}

.telegram-sync-banner--failed {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.08);
}
</style>
