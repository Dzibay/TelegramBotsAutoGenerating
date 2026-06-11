<template>
  <div class="settings-page">
    <header class="page-header">
      <h1>Настройки</h1>
      <p class="subtitle">
        Паузы между сообщениями BotFather при массовом создании ботов.
        Больше интервалы — ниже риск блокировки, но дольше выполнение задачи.
      </p>
    </header>

    <div v-if="loading" class="muted">Загрузка…</div>
    <form v-else class="card form" @submit.prevent="onSave">
      <h3 class="block-title">Интервалы BotFather</h3>

      <div class="settings-grid">
        <div class="form-group">
          <label for="inter-bot">Пауза между ботами (сек.)</label>
          <input
            id="inter-bot"
            v-model.number="form.inter_bot_delay_sec"
            type="number"
            min="10"
            max="600"
            required
          />
          <p class="field-hint">Между завершением одного бота и началом следующего. По умолчанию 45.</p>
        </div>

        <div class="form-group">
          <label for="op-delay">Пауза между командами (сек.)</label>
          <input
            id="op-delay"
            v-model.number="form.op_delay_sec"
            type="number"
            min="0"
            max="60"
            required
          />
          <p class="field-hint">Между /newbot, /setdescription, /setabouttext и т.д. внутри одного бота.</p>
        </div>

        <div class="form-group">
          <label for="conv-delay">Пауза перед диалогом (сек.)</label>
          <input
            id="conv-delay"
            v-model.number="form.conv_delay_sec"
            type="number"
            min="0"
            max="30"
            required
          />
          <p class="field-hint">Короткая задержка перед открытием нового чата с BotFather.</p>
        </div>

        <div class="form-group">
          <label for="batch-size">Размер пакета (ботов)</label>
          <input
            id="batch-size"
            v-model.number="form.batch_size"
            type="number"
            min="1"
            max="50"
            required
          />
          <p class="field-hint">После скольких ботов делать длинную паузу.</p>
        </div>

        <div class="form-group">
          <label for="batch-cooldown">Пауза после пакета (сек.)</label>
          <input
            id="batch-cooldown"
            v-model.number="form.batch_cooldown_sec"
            type="number"
            min="30"
            max="3600"
            required
          />
          <p class="field-hint">Длинный отдых после каждого пакета (например 180 = 3 мин).</p>
        </div>

        <div class="form-group">
          <label for="post-throttle">Пауза после throttle (сек.)</label>
          <input
            id="post-throttle"
            v-model.number="form.post_throttle_delay_sec"
            type="number"
            min="0"
            max="600"
            required
          />
          <p class="field-hint">Дополнительная пауза, если BotFather ответил «too many attempts».</p>
        </div>

        <div class="form-group">
          <label for="flood-wait">Макс. ожидание FloodWait (сек.)</label>
          <input
            id="flood-wait"
            v-model.number="form.max_server_flood_wait"
            type="number"
            min="30"
            max="600"
            required
          />
          <p class="field-hint">
            Если Telegram просит подождать дольше — задача вернёт ошибку вместо многочасового ожидания.
          </p>
        </div>
      </div>

      <div class="preview-box">
        <p class="preview-title">Пример для 10 ботов</p>
        <p class="preview-text">
          Оценка времени: <strong>{{ sampleEta }}</strong>
          ({{ pacingSummary }})
        </p>
      </div>

      <p v-if="loadError" class="error-text">{{ loadError }}</p>
      <p v-if="saveError" class="error-text">{{ saveError }}</p>
      <p v-if="saved" class="success-text">Настройки сохранены</p>

      <div class="actions">
        <button type="button" class="btn-ghost" :disabled="saving" @click="onReset">
          Сбросить к дефолтам
        </button>
        <button type="submit" :disabled="saving">
          {{ saving ? 'Сохранение…' : 'Сохранить' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useSettingsStore } from '../stores/settingsStore';
import {
  estimateBulkCreationSec,
  formatDurationSec,
  formatPacingSummary,
} from '../utils/estimateJobTime';

const settingsStore = useSettingsStore();

const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const loadError = ref(null);
const saveError = ref(null);

const form = ref({
  inter_bot_delay_sec: 45,
  op_delay_sec: 4,
  conv_delay_sec: 2,
  batch_size: 5,
  batch_cooldown_sec: 180,
  post_throttle_delay_sec: 30,
  max_server_flood_wait: 180,
});

const sampleEta = computed(() =>
  formatDurationSec(estimateBulkCreationSec(10, form.value))
);

const pacingSummary = computed(() => formatPacingSummary(form.value));

function applyFromStore() {
  form.value = { ...settingsStore.botfatherPacing };
}

async function onSave() {
  saving.value = true;
  saveError.value = null;
  saved.value = false;
  try {
    await settingsStore.saveBotfatherPacing({ ...form.value });
    applyFromStore();
    saved.value = true;
  } catch (e) {
    saveError.value = e.response?.data?.error || 'Не удалось сохранить';
  } finally {
    saving.value = false;
  }
}

function onReset() {
  form.value = {
    inter_bot_delay_sec: 45,
    op_delay_sec: 4,
    conv_delay_sec: 2,
    batch_size: 5,
    batch_cooldown_sec: 180,
    post_throttle_delay_sec: 30,
    max_server_flood_wait: 180,
  };
}

onMounted(async () => {
  loading.value = true;
  loadError.value = null;
  try {
    await settingsStore.fetchBotfatherPacing();
    applyFromStore();
    if (settingsStore.error) loadError.value = settingsStore.error;
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.settings-page {
  max-width: 720px;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.5;
}

.block-title {
  margin: 0 0 1rem;
  font-size: 1rem;
}

.settings-grid {
  display: grid;
  gap: 1rem;
}

.preview-box {
  margin-top: 1.25rem;
  padding: 0.85rem 1rem;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(59, 130, 246, 0.25);
  background: rgba(59, 130, 246, 0.08);
}

.preview-title {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #93c5fd;
}

.preview-text {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted);
}

.success-text {
  margin: 0.75rem 0 0;
  color: var(--success);
  font-size: 0.875rem;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1.25rem;
}
</style>
