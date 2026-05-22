<template>
  <div class="bot-create">
    <header class="page-header">
      <RouterLink v-if="campaignId" :to="{ name: 'campaign-workspace', params: { id: campaignId }, query: { tab: 'create' } }" class="back">
        ← Создание ботов
      </RouterLink>
      <RouterLink v-else to="/app/bots" class="back">← Боты</RouterLink>
      <h1>Один бот</h1>
      <p class="subtitle">Пошагово: ссылка и аккаунт → ключевая фраза → тексты → создание в Telegram.</p>
    </header>

    <div class="wizard-steps">
      <span :class="{ active: wizardStep >= 1, done: wizardStep > 1 }">1. Основное</span>
      <span :class="{ active: wizardStep >= 2, done: wizardStep > 2 }">2. Фраза</span>
      <span :class="{ active: wizardStep >= 3, done: wizardStep > 3 }">3. Тексты</span>
      <span :class="{ active: wizardStep >= 4 }">4. Создание</span>
    </div>

    <form class="card form" @submit.prevent="onSubmit">
      <div v-show="wizardStep === 1" class="wizard-pane">
      <div class="form-group">
        <label>Ссылка на рекламируемый сервис *</label>
        <input
          v-model="targetUrl"
          type="url"
          required
          placeholder="https://example.com/landing"
        />
        <p class="field-hint">Адрес сайта или лендинга, куда должны переходить пользователи.</p>
      </div>

      <BotLinkModeField v-model="linkMode" :preview-url="linkPreview || ''" />

      <div v-if="!routeCampaignId" class="form-group">
        <label>Кампания</label>
        <select v-model.number="campaignId" required @change="onCampaignChange">
          <option :value="null" disabled>Выберите кампанию</option>
          <option v-for="c in campaigns" :key="c.id" :value="c.id">{{ c.title }}</option>
        </select>
      </div>

      <div class="form-group">
        <label>Аккаунт Telegram</label>
        <select v-model.number="accountId" required :disabled="!usableAccounts.length">
          <option :value="null" disabled>Выберите аккаунт</option>
          <option v-for="a in usableAccounts" :key="a.id" :value="a.id">
            {{ accountOptionLabel(a) }}
          </option>
        </select>
        <p v-if="campaignId && accounts.length && !usableAccounts.length" class="field-hint error-text">
          Нет готовых аккаунтов.
          <RouterLink :to="{ name: 'campaign-workspace', params: { id: campaignId }, query: { tab: 'accounts' } }">
            Добавьте и проверьте аккаунты
          </RouterLink>.
        </p>
      </div>
      <button type="button" class="btn btn-next" :disabled="!canGoStep2" @click="wizardStep = 2">
        Далее: ключевая фраза →
      </button>
      </div>

      <div v-show="wizardStep === 2" class="wizard-pane">
      <div class="form-group">
        <label>Ключевая фраза для этого бота *</label>
        <input
          v-model="keyword"
          type="text"
          required
          placeholder="например: vpn бот бесплатно"
        />
        <p class="field-hint">
          По этой фразе подберутся имя, описание и приветствие. У каждого бота — своя фраза.
        </p>
      </div>
      <div class="wizard-nav">
        <button type="button" class="btn-ghost" @click="wizardStep = 1">← Назад</button>
        <button type="button" class="btn btn-next" :disabled="!keyword.trim()" @click="wizardStep = 3">
          Далее: тексты →
        </button>
      </div>
      </div>

      <div v-show="wizardStep === 3" class="wizard-pane">
      <button
        type="button"
        class="btn-ai"
        :disabled="!campaignId || !accountId || !targetUrl.trim() || !keyword.trim() || generating"
        @click="onGenerate"
      >
        {{ generating ? 'Генерация…' : '✨ Заполнить тексты по фразе' }}
      </button>

      <BotProfileFields
        v-model="form"
        v-model:generate-avatar="generateAvatar"
        :keyword="keyword"
        :avatar-prompt="avatarPrompt"
        :public-link="linkPreview || ''"
        show-generate-on-create
        @update:avatar-file="avatarFile = $event"
      />

      <label class="check">
        <input v-model="autoStart" type="checkbox" />
        Запустить бота сразу после создания
      </label>
      <div class="wizard-nav">
        <button type="button" class="btn-ghost" @click="wizardStep = 2">← Назад</button>
        <button type="button" class="btn btn-next" :disabled="!form.display_name || !form.username" @click="wizardStep = 4">
          Далее: создание →
        </button>
      </div>
      </div>

      <div v-show="wizardStep === 4" class="wizard-pane">
      <p v-if="submitError" class="error-text">{{ submitError }}</p>
      <InlineTaskIndicator v-if="submitting" fallback-label="Создаём бота в Telegram…" />
      <div class="actions">
        <button type="button" class="btn-ghost" @click="wizardStep = 3">← К текстам</button>
        <button type="submit" class="btn" :disabled="submitting || !targetUrl.trim() || !keyword.trim()">
          {{ submitting ? 'Создание…' : 'Создать бота в Telegram' }}
        </button>
      </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import BotProfileFields from '../components/BotProfileFields.vue';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';

const taskStore = useAsyncTaskStore();

const route = useRoute();
const router = useRouter();

const routeCampaignId = route.params.id ? Number(route.params.id) : null;
const wizardStep = ref(1);
const campaigns = ref([]);
const accounts = ref([]);
const campaignId = ref(routeCampaignId || (route.query.campaign_id ? Number(route.query.campaign_id) : null));

const canGoStep2 = computed(
  () => campaignId.value && accountId.value && targetUrl.value.trim() && usableAccounts.value.length
);
const accountId = ref(null);
const targetUrl = ref('');
const keyword = ref('');
const linkMode = ref('redirect');
const redirectSlug = ref(null);
const draftPublicLink = ref(null);
const generating = ref(false);
const submitting = ref(false);
const submitError = ref(null);
const autoStart = ref(true);
const generateAvatar = ref(true);
const avatarFile = ref(null);
const avatarPrompt = ref('');
const form = ref({
  display_name: '',
  username: '',
  description: '',
  about_text: '',
  welcome_message: '',
  welcome_button_enabled: true,
  welcome_button_text: 'Перейти по ссылке',
});

const STATUS_LABELS = {
  ready: 'готов',
  creating: 'создание',
  pending: 'ожидание',
  error: 'ошибка',
  exhausted: 'лимит ботов',
  disabled: 'отключён',
};

const linkPreview = computed(() => {
  if (draftPublicLink.value) return draftPublicLink.value;
  if (linkMode.value === 'direct' && targetUrl.value.trim()) return targetUrl.value.trim();
  return null;
});

const usableAccounts = computed(() =>
  accounts.value.filter((a) => {
    if (a.status === 'disabled') return false;
    if (a.bots_created >= a.max_bots_limit) return false;
    return ['ready', 'creating', 'pending', 'error', 'exhausted'].includes(a.status);
  }),
);

function accountOptionLabel(a) {
  const name = a.label || a.phone || `#${a.id}`;
  const st = STATUS_LABELS[a.status] || a.status;
  return `${name} — ${st} (${a.bots_created}/${a.max_bots_limit} ботов)`;
}

async function loadCampaigns() {
  campaigns.value = await campaignService.list();
  if (campaignId.value) {
    const c = campaigns.value.find((x) => x.id === campaignId.value);
    if (c?.resource_url && !targetUrl.value) {
      targetUrl.value = c.resource_url;
    }
  }
}

async function loadAccounts() {
  if (!campaignId.value) {
    accounts.value = [];
    return;
  }
  accounts.value = await campaignService.getAccounts(campaignId.value);
  const pick = usableAccounts.value.find((a) => a.status === 'ready' || a.status === 'creating')
    ?? usableAccounts.value[0];
  accountId.value = pick?.id ?? null;
}

async function loadKeywordContext() {
  if (!campaignId.value) {
    keyword.value = '';
    return;
  }
  /* keyword вводится вручную для каждого бота */
}

async function onCampaignChange() {
  accountId.value = null;
  keyword.value = '';
  const c = campaigns.value.find((x) => x.id === campaignId.value);
  if (c?.resource_url) targetUrl.value = c.resource_url;
  await loadAccounts();
  await loadKeywordContext();
}

async function onGenerate() {
  generating.value = true;
  submitError.value = null;
  try {
    const draft = await botService.generateDraft({
      campaignId: campaignId.value,
      accountId: accountId.value,
      targetUrl: targetUrl.value.trim(),
      keyword: keyword.value || undefined,
      redirectSlug: redirectSlug.value,
      linkMode: linkMode.value,
    });
    redirectSlug.value = draft.redirect_slug;
    draftPublicLink.value = draft.public_link;
    if (draft.link_mode) linkMode.value = draft.link_mode;
    targetUrl.value = draft.target_url || targetUrl.value;
    form.value.display_name = draft.display_name;
    form.value.username = draft.username;
    form.value.description = draft.description;
    form.value.about_text = draft.about_text || '';
    form.value.welcome_message = draft.welcome_message;
    form.value.welcome_button_enabled = draft.welcome_button_enabled !== false;
    form.value.welcome_button_text = draft.welcome_button_text || 'Перейти по ссылке';
    avatarPrompt.value = draft.avatar_prompt || '';
    if (draft.keyword) keyword.value = draft.keyword;
    if (draft.ai_hint) {
      submitError.value = draft.ai_hint;
    }
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Ошибка генерации AI';
  } finally {
    generating.value = false;
  }
}

async function onSubmit() {
  submitting.value = true;
  submitError.value = null;
  const uname = form.value.username.replace(/^@/, '');
  try {
    const bot = await taskStore.run(
      'CREATE_BOT',
      () =>
        botService.create(
          {
            campaign_id: campaignId.value,
            telegram_account_id: accountId.value,
            target_url: targetUrl.value.trim(),
            display_name: form.value.display_name,
            username: uname,
            description: form.value.description,
            about_text: form.value.about_text,
            welcome_message: form.value.welcome_message,
            welcome_button_enabled: form.value.welcome_button_enabled,
            welcome_button_text: form.value.welcome_button_text,
            keyword: keyword.value || null,
            redirect_slug: redirectSlug.value,
            link_mode: linkMode.value,
            create_via_botfather: true,
            auto_start: autoStart.value,
            generate_avatar: generateAvatar.value,
          },
          avatarFile.value
        ),
      { username: uname }
    );
    router.push({ name: 'bot-edit', params: { id: bot.id }, query: { created: '1' } });
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
  await loadKeywordContext();
});
</script>

<style scoped>
.bot-create {
  max-width: 560px;
}

.wizard-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.wizard-steps span {
  flex: 1;
  min-width: 5rem;
  text-align: center;
  padding: 0.4rem 0.5rem;
  font-size: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  color: var(--muted);
}

.wizard-steps span.active {
  border-color: var(--accent);
  color: var(--text);
  background: rgba(59, 130, 246, 0.1);
}

.wizard-steps span.done {
  color: #86efac;
  border-color: rgba(34, 197, 94, 0.35);
}

.wizard-nav {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.wizard-nav .btn-next {
  flex: 1;
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

.preview-tracking {
  margin-bottom: 1rem;
  padding: 0.65rem 0.75rem;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.preview-label {
  display: block;
  font-size: 0.75rem;
  color: var(--muted);
  margin-bottom: 0.35rem;
}

.preview-tracking code {
  font-size: 0.8rem;
  word-break: break-all;
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

.actions .btn {
  flex: 1;
}
</style>
