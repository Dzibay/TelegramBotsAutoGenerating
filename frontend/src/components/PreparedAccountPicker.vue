<template>
  <div class="picker">
    <p v-if="loading" class="muted">Загрузка аккаунтов…</p>
    <p v-else-if="loadError" class="error-text">{{ loadError }}</p>
    <p v-else-if="!accounts.length" class="muted empty">
      Нет свободных подготовленных аккаунтов.
      <RouterLink to="/app/accounts/prepare">Подготовьте аккаунты</RouterLink>
      и вернитесь сюда.
    </p>
    <ul v-else class="acc-pick-list">
      <li v-for="a in accounts" :key="a.id">
        <label class="pick-row">
          <input
            type="checkbox"
            :value="a.id"
            :checked="modelValue.includes(a.id)"
            @change="toggle(a.id, $event.target.checked)"
          />
          <span class="pick-info">
            <strong>{{ displayName(a) }}</strong>
            <span v-if="a.username" class="sub">@{{ a.username }}</span>
            <span v-if="a.phone" class="sub">{{ a.phone }}</span>
          </span>
          <StatusBadge :status="a.status" />
        </label>
      </li>
    </ul>
    <p v-if="accounts.length" class="pick-meta">
      Выбрано: {{ modelValue.length }} из {{ accounts.length }}
    </p>
  </motion.div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import StatusBadge from './StatusBadge.vue';
import { preparedAccountService } from '../services/preparedAccountService';

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
});

const emit = defineEmits(['update:modelValue']);

const accounts = ref([]);
const loading = ref(true);
const loadError = ref(null);

function displayName(a) {
  return a.label || a.phone || a.username || `Аккаунт #${a.id}`;
}

function toggle(id, checked) {
  const next = new Set(props.modelValue);
  if (checked) next.add(id);
  else next.delete(id);
  emit('update:modelValue', [...next]);
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    accounts.value = await preparedAccountService.listAvailable();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось загрузить пул аккаунтов';
  } finally {
    loading.value = false;
  }
}

onMounted(load);

defineExpose({ reload: load });
</script>

<style scoped>
.picker {
  margin-top: 0.5rem;
}

.empty {
  font-size: 0.875rem;
  line-height: 1.5;
}

.acc-pick-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  max-height: 280px;
  overflow-y: auto;
}

.pick-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.85rem;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}

.pick-row:last-child {
  border-bottom: none;
}

.pick-row input {
  width: auto;
  flex-shrink: 0;
}

.pick-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.pick-info strong {
  font-size: 0.9rem;
}

.sub {
  font-size: 0.8rem;
  color: var(--muted);
}

.pick-meta {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}
</style>
