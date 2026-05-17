<template>
  <section class="card accounts-panel">
    <div class="panel-head">
      <div>
        <h3>Аккаунты Telegram</h3>
        <p class="panel-desc">
          После добавления из пула аккаунты проверяются автоматически. Перед массовым созданием
          убедитесь, что статус «Готов».
        </p>
      </div>
      <div v-if="accounts.length" class="head-actions">
        <button
          type="button"
          class="btn btn-sm btn-ghost"
          :disabled="verifyingAll || busy"
          @click="$emit('verify-all')"
        >
          {{ verifyingAll ? 'Проверка…' : 'Проверить все' }}
        </button>
      </div>
    </div>

    <div v-if="summary" class="summary" :class="summaryClass">
      {{ summary }}
    </div>

    <p v-if="!accounts.length" class="muted empty">Нет аккаунтов в кампании</p>

    <ul v-else class="account-list">
      <li
        v-for="a in accounts"
        :key="a.id"
        class="account-card"
        :class="{ 'account-card--ok': a.status === 'ready', 'account-card--err': a.status === 'error' }"
      >
        <div class="acc-top">
          <div class="acc-title">
            <strong>{{ a.label || a.phone || `Аккаунт #${a.id}` }}</strong>
            <span v-if="a.phone" class="phone">{{ a.phone }}</span>
          </div>
          <StatusBadge :status="a.status" />
        </div>

        <p class="acc-meta">
          Ботов: {{ a.bots_created }} / {{ a.max_bots_limit }}
          <span v-if="a.tdata_on_disk === false" class="warn-tag">· нет tdata</span>
          <span v-else-if="a.can_create_bots" class="ok-tag">· можно создавать ботов</span>
        </p>

        <p v-if="a.health_hint" class="health-hint">{{ a.health_hint }}</p>
        <p v-if="a.last_error && a.status === 'error'" class="last-error">{{ a.last_error }}</p>
        <p v-if="a.verify_message" class="verify-msg" :class="a.verified ? 'ok' : 'err'">
          {{ a.verify_message }}
        </p>

        <div class="acc-actions">
          <button
            type="button"
            class="btn btn-sm btn-ghost"
            :disabled="busyId === a.id || busy"
            @click="$emit('verify', a)"
          >
            {{ busyId === a.id ? 'Проверка…' : 'Проверить' }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-ghost danger"
            :disabled="busyId === a.id || busy"
            @click="$emit('remove', a)"
          >
            Убрать
          </button>
        </div>
      </li>
    </ul>

    <div v-if="canAdd" class="add-prepared">
      <p class="muted small">Добавить из пула подготовленных</p>
      <PreparedAccountPicker ref="pickerRef" v-model="selectedIds" />
      <button
        type="button"
        class="btn btn-add"
        :disabled="!selectedIds.length || attaching"
        @click="onAttach"
      >
        {{ attaching ? 'Добавление и проверка…' : 'Добавить и проверить' }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import PreparedAccountPicker from './PreparedAccountPicker.vue';
import StatusBadge from './StatusBadge.vue';

const props = defineProps({
  accounts: { type: Array, default: () => [] },
  canAdd: { type: Boolean, default: true },
  attaching: { type: Boolean, default: false },
  verifyingAll: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  busyId: { type: Number, default: null },
  attachMessage: { type: String, default: null },
});

const emit = defineEmits(['attach', 'verify', 'verify-all', 'remove']);

const selectedIds = ref([]);
const pickerRef = ref(null);

const readyCount = computed(() => props.accounts.filter((a) => a.status === 'ready').length);
const errorCount = computed(() => props.accounts.filter((a) => a.status === 'error').length);

const summary = computed(() => {
  if (props.attachMessage) return props.attachMessage;
  if (!props.accounts.length) return null;
  return `Готовых: ${readyCount.value} · с ошибкой: ${errorCount.value} · всего: ${props.accounts.length}`;
});

const summaryClass = computed(() => {
  if (errorCount.value > 0) return 'summary--warn';
  if (readyCount.value > 0) return 'summary--ok';
  return '';
});

function onAttach() {
  if (!selectedIds.value.length) return;
  emit('attach', [...selectedIds.value]);
  selectedIds.value = [];
}

defineExpose({
  reloadPicker: () => pickerRef.value?.reload?.(),
});
</script>

<style scoped>
.accounts-panel {
  padding: 1rem;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.panel-head h3 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}

.panel-desc {
  margin: 0;
  font-size: 0.8rem;
  color: var(--muted);
  max-width: 28rem;
}

.head-actions {
  flex-shrink: 0;
}

.summary {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  font-size: 0.85rem;
}

.summary--ok {
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #86efac;
}

.summary--warn {
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.35);
  color: #fde047;
}

.empty {
  margin: 0;
}

.account-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.account-card {
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
}

.account-card--ok {
  border-color: rgba(34, 197, 94, 0.35);
}

.account-card--err {
  border-color: rgba(239, 68, 68, 0.4);
}

.acc-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.acc-title strong {
  display: block;
}

.phone {
  font-size: 0.8rem;
  color: var(--muted);
}

.acc-meta {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.warn-tag {
  color: #f87171;
}

.ok-tag {
  color: #4ade80;
}

.health-hint,
.last-error,
.verify-msg {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
}

.last-error {
  color: #f87171;
}

.verify-msg.ok {
  color: #4ade80;
}

.verify-msg.err {
  color: #f87171;
}

.acc-actions {
  display: flex;
  gap: 0.35rem;
  margin-top: 0.5rem;
}

.add-prepared {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.add-prepared .small {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
}

.btn-add {
  width: 100%;
  margin-top: 0.75rem;
}
</style>
