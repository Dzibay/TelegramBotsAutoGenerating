<template>
  <div class="create-page">
    <header class="page-header">
      <h1>Новая кампания</h1>
      <p class="subtitle">Название, ссылка на сервис и аккаунты. Ботов добавите на шаге «Боты» в кампании.</p>
    </header>

    <div class="steps">
      <div class="step" :class="{ active: step >= 1, done: step > 1 }">1. Название</div>
      <div class="step" :class="{ active: step >= 2 }">2. Аккаунты</div>
    </div>

    <form class="card form" @submit.prevent="onSubmit">
      <section v-show="step === 1">
        <div class="form-group">
          <label for="title">Название кампании</label>
          <input
            id="title"
            v-model="form.title"
            required
            placeholder="Например: Аккаунты май 2026"
            autofocus
          />
          <p class="field-hint">Удобное имя для вашей группы аккаунтов и ботов</p>
        </div>
        <div class="form-group">
          <label for="resource_url">Ссылка на ваш сервис</label>
          <input
            id="resource_url"
            v-model="form.resource_url"
            type="url"
            placeholder="https://example.com"
          />
          <p class="field-hint">Куда будут вести боты. Можно изменить позже.</p>
        </div>
        <button type="button" class="btn btn-next" :disabled="!form.title.trim()" @click="step = 2">
          Далее: аккаунты →
        </button>
      </section>

      <section v-show="step === 2">
        <div class="form-group">
          <label>Подготовленные аккаунты</label>
          <p class="field-hint">
            Сначала подготовьте аккаунты на странице
            <RouterLink to="/app/accounts/prepare">«Подготовка аккаунтов»</RouterLink>.
          </p>
          <PreparedAccountPicker v-model="selectedPreparedIds" />
        </div>

        <div class="summary card-inner" v-if="form.title">
          <ul>
            <li><strong>Название:</strong> {{ form.title }}</li>
            <li><strong>Аккаунтов:</strong> {{ selectedPreparedIds.length }}</li>
          </ul>
        </div>

        <p v-if="submitError" class="error-text">{{ submitError }}</p>
        <InlineTaskIndicator v-if="submitting" fallback-label="Создаём кампанию и проверяем аккаунты…" />
        <div class="nav-row">
          <button type="button" class="btn-ghost" @click="step = 1">← Назад</button>
          <button type="submit" :disabled="submitting || !selectedPreparedIds.length">
            {{ submitting ? 'Создание…' : 'Создать кампанию' }}
          </button>
        </div>
      </section>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import PreparedAccountPicker from '../components/PreparedAccountPicker.vue';
import { campaignService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { useWorkflowStore } from '../stores/workflowStore';

const taskStore = useAsyncTaskStore();
const workflow = useWorkflowStore();

const router = useRouter();
const step = ref(1);
const submitting = ref(false);
const submitError = ref(null);
const selectedPreparedIds = ref([]);
const form = ref({ title: '', resource_url: '' });

async function onSubmit() {
  if (!selectedPreparedIds.value.length) {
    submitError.value = 'Выберите хотя бы один подготовленный аккаунт';
    step.value = 2;
    return;
  }
  submitting.value = true;
  submitError.value = null;
  try {
    const data = await taskStore.run(
      'CREATE_CAMPAIGN_FULL',
      () =>
        campaignService.createFull({
          payload: {
            title: form.value.title.trim(),
            resource_url: form.value.resource_url.trim() || null,
          },
          preparedAccountIds: selectedPreparedIds.value,
          autoStart: false,
        }),
      { count: selectedPreparedIds.value.length }
    );
    workflow.setCampaign(data.campaign?.id, data.campaign?.title);
    router.push({ name: 'campaign-workspace', params: { id: data.campaign?.id }, query: { tab: 'accounts' } });
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

.summary ul {
  margin: 0;
  padding-left: 1.1rem;
  color: var(--muted);
  font-size: 0.9rem;
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
  margin-top: 0.5rem;
  cursor: pointer;
}

.checkbox-row input {
  width: auto;
}
</style>
