<template>
  <div class="create-page">
    <header class="page-header">
      <RouterLink to="/app" class="back">← Кампании</RouterLink>
      <h1>Новая кампания</h1>
      <p class="subtitle">Заполните данные, выберите подготовленные аккаунты и запустите создание ботов</p>
    </header>

    <div class="steps">
      <div class="step" :class="{ active: step >= 1, done: step > 1 }">1. Ниша</div>
      <div class="step" :class="{ active: step >= 2, done: step > 2 }">2. Аккаунты</div>
      <div class="step" :class="{ active: step >= 3 }">3. Запуск</div>
    </div>

    <form class="card form" @submit.prevent="onSubmit">
      <section v-show="step === 1">
        <div class="form-group">
          <label for="title">Название кампании</label>
          <input id="title" v-model="form.title" required placeholder="Например: Крипто сигналы Q1" />
        </div>
        <div class="form-group">
          <label for="resource">Ссылка на основной ресурс</label>
          <input
            id="resource"
            v-model="form.resource_url"
            type="url"
            required
            placeholder="https://t.me/your_channel"
          />
        </div>
        <div class="form-group">
          <label for="niche">Описание ниши</label>
          <textarea
            id="niche"
            v-model="form.niche_description"
            rows="3"
            placeholder="Кому адресованы боты, какой оффер, тон общения…"
          />
        </div>
        <div class="form-group">
          <label for="keywords">Ключевые слова</label>
          <input
            id="keywords"
            v-model="keywordsRaw"
            required
            placeholder="крипто, сигналы, трейдинг, bitcoin"
          />
          <p class="field-hint">Через запятую — AI распределит их по ботам</p>
        </div>
        <button type="button" class="btn-next" @click="step = 2">Далее: аккаунты →</button>
      </section>

      <section v-show="step === 2">
        <div class="form-group">
          <label>Telegram-аккаунты (tdata)</label>
          <AccountDropzone v-model="accountFiles" />
          <p class="field-hint">
            Каждый ZIP — отдельный аккаунт. Внутри должна быть папка <code>tdata</code> из Telegram Desktop.
          </p>
        </div>
        <div class="nav-row">
          <button type="button" class="btn-ghost" @click="step = 1">← Назад</button>
          <button type="button" :disabled="!accountFiles.length" @click="step = 3">Далее →</button>
        </div>
      </section>

      <section v-show="step === 3">
        <div class="summary card-inner">
          <h3>Проверьте перед запуском</h3>
          <ul>
            <li><strong>Название:</strong> {{ form.title }}</li>
            <li><strong>Ресурс:</strong> {{ form.resource_url }}</li>
            <li><strong>Ключевые слова:</strong> {{ parsedKeywords.join(', ') }}</li>
            <li><strong>Аккаунтов:</strong> {{ selectedPreparedIds.length }}</li>
          </ul>
        </div>
        <label class="checkbox-row">
          <input v-model="autoStart" type="checkbox" />
          Сразу запустить создание ботов после сохранения
        </label>
        <p v-if="submitError" class="error-text">{{ submitError }}</p>
        <div class="nav-row">
          <button type="button" class="btn-ghost" @click="step = 2">← Назад</button>
          <button type="submit" :disabled="submitting">
            {{ submitting ? 'Создание…' : 'Создать кампанию' }}
          </button>
        </div>
      </section>
    </form>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import PreparedAccountPicker from '../components/PreparedAccountPicker.vue';
import { campaignService } from '../services/campaignService';

const router = useRouter();
const step = ref(1);
const submitting = ref(false);
const submitError = ref(null);
const selectedPreparedIds = ref([]);
const autoStart = ref(true);
const keywordsRaw = ref('');
const form = ref({
  title: '',
  resource_url: '',
  niche_description: '',
});

const parsedKeywords = computed(() =>
  keywordsRaw.value
    .split(',')
    .map((k) => k.trim())
    .filter(Boolean)
);

async function onSubmit() {
  if (!selectedPreparedIds.value.length) {
    submitError.value = 'Выберите хотя бы один подготовленный аккаунт';
    step.value = 2;
    return;
  }
  submitting.value = true;
  submitError.value = null;
  try {
    const data = await campaignService.createFull({
      payload: {
        title: form.value.title,
        resource_url: form.value.resource_url,
        niche_description: form.value.niche_description || null,
        keywords: parsedKeywords.value,
      },
      preparedAccountIds: selectedPreparedIds.value,
      autoStart: autoStart.value,
    });
    const id = data.campaign?.id;
    router.push({ name: 'campaign-detail', params: { id } });
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Не удалось создать кампанию';
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.create-page {
  max-width: 640px;
}

.page-header {
  margin-bottom: 1.5rem;
}

.back {
  font-size: 0.875rem;
  display: inline-block;
  margin-bottom: 0.5rem;
}

.page-header h1 {
  margin: 0;
  font-size: 1.5rem;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.steps {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

.step {
  flex: 1;
  text-align: center;
  padding: 0.5rem;
  font-size: 0.8rem;
  border-radius: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--muted);
}

.step.active {
  border-color: var(--accent);
  color: var(--text);
}

.step.done {
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.4);
}

.field-hint {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.field-hint code {
  font-size: 0.85em;
  background: var(--bg);
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
}

.btn-next {
  width: 100%;
  margin-top: 0.5rem;
}

.nav-row {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.nav-row button:last-child {
  flex: 1;
}

.summary h3 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
}

.summary ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--muted);
  font-size: 0.9rem;
}

.summary li {
  margin-bottom: 0.35rem;
}

.card-inner {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  margin-bottom: 1rem;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  font-size: 0.9rem;
  cursor: pointer;
}

.checkbox-row input {
  width: auto;
}
</style>
