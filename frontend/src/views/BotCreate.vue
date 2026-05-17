<template>
  <div class="bot-create">
    <header class="page-header">
      <RouterLink to="/app/bots" class="back">← Боты</RouterLink>
      <h1>Создание бота</h1>
      <p class="subtitle">Выберите кампанию и аккаунт, сгенерируйте контент через AI и создайте бота в BotFather</p>
    </header>

    <form class="card form" @submit.prevent="onSubmit">
      <div class="form-group">
        <label>Кампания</label>
        <select v-model.number="campaignId" required @change="onCampaignChange">
          <option :value="null" disabled>Выберите кампанию</option>
          <option v-for="c in campaigns" :key="c.id" :value="c.id">{{ c.title }}</option>
        </select>
      </div>

      <div class="form-group">
        <label>Аккаунт Telegram</label>
        <select v-model.number="accountId" required :disabled="!accounts.length">
          <option :value="null" disabled>Выберите аккаунт</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">
            {{ a.label || a.phone || `#${a.id}` }}
            ({{ a.bots_created }}/{{ a.max_bots_limit }} ботов)
          </option>
        </select>
        <p v-if="campaignId && !accounts.length" class="field-hint">
          В кампании нет аккаунтов.
          <RouterLink :to="{ name: 'campaign-detail', params: { id: campaignId } }">Добавьте подготовленные</RouterLink>
        </p>
      </div>

      <div class="form-group">
        <label>Ключевое слово (для AI)</label>
        <input v-model="keyword" placeholder="Необязательно — возьмётся из кампании" />
      </div>

      <button
        type="button"
        class="btn-ai"
        :disabled="!campaignId || !accountId || generating"
        @click="onGenerate"
      >
        {{ generating ? 'Генерация…' : '✨ Сгенерировать поля через AI' }}
      </button>

      <div class="form-group">
        <label>Имя бота</label>
        <input v-model="form.display_name" required maxlength="64" />
      </div>
      <div class="form-group">
        <label>Username (@)</label>
        <input v-model="form.username" required placeholder="my_bot" />
      </div>
      <div class="form-group">
        <label>Описание</label>
        <textarea v-model="form.description" rows="3" maxlength="512" />
      </div>
      <div class="form-group">
        <label>Приветственное сообщение</label>
        <textarea v-model="form.welcome_message" rows="4" required />
      </div>

      <label class="check">
        <input v-model="autoStart" type="checkbox" />
        Запустить бота сразу после создания
      </label>

      <p v-if="submitError" class="error-text">{{ submitError }}</p>
      <div class="actions">
        <RouterLink to="/app/bots" class="btn-ghost">Отмена</RouterLink>
        <button type="submit" :disabled="submitting">
          {{ submitting ? 'Создание…' : 'Создать бота' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';

const route = useRoute();
const router = useRouter();

const campaigns = ref([]);
const accounts = ref([]);
const campaignId = ref(route.query.campaign_id ? Number(route.query.campaign_id) : null);
const accountId = ref(null);
const keyword = ref('');
const generating = ref(false);
const submitting = ref(false);
const submitError = ref(null);
const autoStart = ref(true);
const form = ref({
  display_name: '',
  username: '',
  description: '',
  welcome_message: '',
});

async function loadCampaigns() {
  campaigns.value = await campaignService.list();
}

async function loadAccounts() {
  if (!campaignId.value) {
    accounts.value = [];
    return;
  }
  accounts.value = await campaignService.getAccounts(campaignId.value);
  if (accounts.value.length && !accountId.value) {
    const free = accounts.value.find((a) => a.bots_created < a.max_bots_limit);
    accountId.value = free?.id ?? accounts.value[0].id;
  }
}

function onCampaignChange() {
  accountId.value = null;
  loadAccounts();
}

async function onGenerate() {
  generating.value = true;
  submitError.value = null;
  try {
    const draft = await botService.generateDraft({
      campaignId: campaignId.value,
      accountId: accountId.value,
      keyword: keyword.value || undefined,
    });
    form.value.display_name = draft.display_name;
    form.value.username = draft.username;
    form.value.description = draft.description;
    form.value.welcome_message = draft.welcome_message;
    if (draft.keyword) keyword.value = draft.keyword;
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Ошибка генерации AI';
  } finally {
    generating.value = false;
  }
}

async function onSubmit() {
  submitting.value = true;
  submitError.value = null;
  try {
    const bot = await botService.create({
      campaign_id: campaignId.value,
      telegram_account_id: accountId.value,
      display_name: form.value.display_name,
      username: form.value.username.replace(/^@/, ''),
      description: form.value.description,
      welcome_message: form.value.welcome_message,
      keyword: keyword.value || null,
      create_via_botfather: true,
      auto_start: autoStart.value,
    });
    router.push({ name: 'bot-edit', params: { id: bot.id } });
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Не удалось создать бота';
  } finally {
    submitting.value = false;
  }
}

watch(campaignId, loadAccounts);
onMounted(async () => {
  await loadCampaigns();
  await loadAccounts();
});
</script>

<style scoped>
.bot-create {
  max-width: 560px;
}

.page-header {
  margin-bottom: 1.25rem;
}

.back {
  font-size: 0.875rem;
  color: var(--muted);
}

.page-header h1 {
  margin: 0.35rem 0 0;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.field-hint {
  font-size: 0.8rem;
  color: var(--muted);
  margin-top: 0.35rem;
}

.btn-ai {
  width: 100%;
  margin: 0.5rem 0 1rem;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
}

.check {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 1rem 0;
  font-size: 0.9rem;
  cursor: pointer;
}

.check input {
  width: auto;
}

.actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.actions button[type='submit'] {
  flex: 1;
}
</style>
