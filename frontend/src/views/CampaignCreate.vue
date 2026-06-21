<template>
  <div class="create-page">
    <header class="page-header">
      <h1>Новая кампания</h1>
      <p class="subtitle">Укажите название и ссылку на сервис. Аккаунты и ботов можно добавить позже.</p>
    </header>

    <form class="card form" @submit.prevent="onSubmit">
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

      <details class="optional-accounts">
        <summary>Аккаунты (необязательно)</summary>
        <p class="field-hint">
          Можно добавить подготовленные аккаунты сразу или позже в кампании.
          <RouterLink to="/app/accounts/prepare">Подготовка аккаунтов</RouterLink>
        </p>
        <PreparedAccountPicker v-model="selectedPreparedIds" />
        <p v-if="selectedPreparedIds.length" class="pick-summary">
          Выбрано аккаунтов: {{ selectedPreparedIds.length }}
        </p>
      </details>

      <p v-if="submitError" class="error-text">{{ submitError }}</p>
      <OperationStatus
        v-if="submitting"
        :message="taskStore.serverProgressMessage"
        :status="taskStore.serverJobStatus"
      />
      <InlineTaskIndicator
        v-if="submitting"
        :fallback-label="selectedPreparedIds.length ? 'Создаём кампанию и проверяем аккаунты…' : 'Создаём кампанию…'"
      />
      <button type="submit" :disabled="submitting || !form.title.trim()">
        {{ submitting ? 'Создание…' : 'Создать кампанию' }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { formatApiError } from '../utils/apiErrorMessage.js';
import { ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import OperationStatus from '../components/OperationStatus.vue';
import PreparedAccountPicker from '../components/PreparedAccountPicker.vue';
import { campaignService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { useWorkflowStore } from '../stores/workflowStore';

const taskStore = useAsyncTaskStore();
const workflow = useWorkflowStore();

const router = useRouter();
const submitting = ref(false);
const submitError = ref(null);
const selectedPreparedIds = ref([]);
const form = ref({ title: '', resource_url: '' });

async function onSubmit() {
  submitting.value = true;
  submitError.value = null;
  try {
    const payload = {
      title: form.value.title.trim(),
      resource_url: form.value.resource_url.trim() || null,
    };
    const hasAccounts = selectedPreparedIds.value.length > 0;

    const data = await taskStore.run(
      hasAccounts ? 'CREATE_CAMPAIGN_FULL' : 'CREATE_CAMPAIGN',
      async ({ logStep, setServerProgress }) => {
        if (hasAccounts) {
          logStep('POST create-full', 'debug', { accounts: selectedPreparedIds.value.length });
          setServerProgress('Создаём кампанию и добавляем аккаунты…', 'running');
          const res = await campaignService.createFull({
            payload,
            preparedAccountIds: selectedPreparedIds.value,
            autoStart: false,
          });
          const summary = res.verify_summary;
          if (summary) {
            setServerProgress(
              `Проверено: ${summary.verified ?? 0}/${summary.total ?? selectedPreparedIds.value.length}`,
              'completed'
            );
          }
          logStep(`Кампания #${res.campaign?.id} создана`, 'success', summary);
          return res;
        }
        logStep('POST /campaigns', 'debug');
        setServerProgress('Создаём кампанию…', 'running');
        const campaign = await campaignService.create(payload);
        setServerProgress('Кампания создана', 'completed');
        logStep(`Кампания #${campaign?.id} создана`, 'success');
        return { campaign };
      },
      hasAccounts ? { count: selectedPreparedIds.value.length } : undefined
    );

    workflow.setCampaign(data.campaign?.id, data.campaign?.title);
    router.push({
      name: 'campaign-workspace',
      params: { id: data.campaign?.id },
      query: { tab: hasAccounts ? 'accounts' : 'guide' },
    });
  } catch (e) {
    submitError.value = formatApiError(e, 'Не удалось создать кампанию');
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.create-page {
  max-width: 640px;
}

.optional-accounts {
  margin: 1rem 0;
  padding: 0.85rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: rgba(8, 12, 20, 0.4);
}

.optional-accounts summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
}

.pick-summary {
  margin: 0.75rem 0 0;
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
