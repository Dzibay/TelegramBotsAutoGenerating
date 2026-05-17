<template>
  <div class="bot-create">
    <header class="page-header">
      <RouterLink to="/app/bots" class="back">← Боты</RouterLink>
      <h1>Создание бота</h1>
      <p class="subtitle">
        Укажите ссылку на рекламируемый сервис — в боте будет трекинг-ссылка с подсчётом кликов
      </p>
    </header>

    <form class="card form" @submit.prevent="onSubmit">
      <div class="form-group">
        <label>Ссылка на рекламируемый сервис *</label>
        <input
          v-model="targetUrl"
          type="url"
          required
          placeholder="https://example.com/landing"
        />
        <p class="field-hint">Прямая ссылка. В боте пользователи увидят защищённую ссылку вида /go/…</p>
      </div>

      <div v-if="draftTrackingUrl" class="preview-tracking card-inner">
        <span class="preview-label">Трекинг-ссылка (будет в боте):</span>
        <code>{{ draftTrackingUrl }}</code>
      </div>

      <div class="form-group">
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
          Нет готовых аккаунтов. Добавьте подготовленные в
          <RouterLink :to="{ name: 'campaign-detail', params: { id: campaignId } }">кампанию</RouterLink>
          (статус должен быть «готов»).
        </p>
      </div>

      <div class="form-group">
        <label>Ключевое слово бота *</label>
        <select v-model="keyword" required :disabled="!campaignKeywords.length">
          <option value="" disabled>Выберите ключевое слово</option>
          <option v-for="kw in campaignKeywords" :key="kw" :value="kw">
            {{ kw }}{{ usedKeywords.has(kw.toLowerCase()) ? ' (уже есть бот)' : '' }}
          </option>
        </select>
        <p v-if="campaignId && !campaignKeywords.length" class="field-hint error-text">
          В кампании нет ключевых слов.
          <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }">Сгенерируйте в настройках</RouterLink>
        </p>
        <p v-else class="field-hint">
          Каждый бот заточен под одно поисковое слово. Тексты AI строятся вокруг выбранной фразы.
        </p>
      </div>

      <button
        type="button"
        class="btn-ai"
        :disabled="!campaignId || !accountId || !targetUrl.trim() || !keyword || generating"
        @click="onGenerate"
      >
        {{ generating ? 'Генерация…' : '✨ Сгенерировать поля (переезд + ссылка)' }}
      </button>

      <div class="form-group">
        <label>Имя бота</label>
        <input v-model="form.display_name" required maxlength="64" />
      </div>
      <div class="form-group">
        <label>Username (@)</label>
        <input v-model="form.username" required placeholder="my_service_bot" />
        <p class="field-hint">
          Только латиница, цифры и _, 5–32 символа, обязательно окончание <code>bot</code>
          (например: promo_shop_bot). После сохранения будет нормализован автоматически.
        </p>
      </div>
      <div class="form-group">
        <label>Описание (до старта чата)</label>
        <textarea v-model="form.description" rows="4" maxlength="512" />
        <p class="field-hint">Текст «бот переехал» и трекинг-ссылка подставляются автоматически</p>
      </div>
      <div class="form-group">
        <label>Сообщение /start</label>
        <textarea v-model="form.welcome_message" rows="5" required />
      </div>

      <label class="check">
        <input v-model="autoStart" type="checkbox" />
        Запустить бота сразу после создания
      </label>

      <p v-if="submitError" class="error-text">{{ submitError }}</p>
      <div class="actions">
        <RouterLink to="/app/bots" class="btn-ghost">Отмена</RouterLink>
        <button type="submit" class="btn" :disabled="submitting || !targetUrl.trim()">
          {{ submitting ? 'Создание…' : 'Создать бота' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';

const route = useRoute();
const router = useRouter();

const campaigns = ref([]);
const accounts = ref([]);
const campaignId = ref(route.query.campaign_id ? Number(route.query.campaign_id) : null);
const accountId = ref(null);
const targetUrl = ref('');
const keyword = ref('');
const campaignKeywords = ref([]);
const usedKeywords = ref(new Set());
const redirectSlug = ref(null);
const draftTrackingUrl = ref(null);
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

const STATUS_LABELS = {
  ready: 'готов',
  creating: 'создание',
  pending: 'ожидание',
  error: 'ошибка',
  exhausted: 'лимит',
  disabled: 'отключён',
};

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
    campaignKeywords.value = [];
    usedKeywords.value = new Set();
    keyword.value = '';
    return;
  }
  const c = campaigns.value.find((x) => x.id === campaignId.value);
  campaignKeywords.value = c?.keywords || [];
  try {
    const data = await campaignService.suggestKeyword(campaignId.value);
    usedKeywords.value = new Set((data.used_keywords || []).map((k) => k.toLowerCase()));
    if (data.keyword) keyword.value = data.keyword;
    if (data.keywords?.length) campaignKeywords.value = data.keywords;
  } catch {
    if (campaignKeywords.value.length && !keyword.value) {
      keyword.value = campaignKeywords.value[0];
    }
  }
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
    });
    redirectSlug.value = draft.redirect_slug;
    draftTrackingUrl.value = draft.tracking_url;
    targetUrl.value = draft.target_url || targetUrl.value;
    form.value.display_name = draft.display_name;
    form.value.username = draft.username;
    form.value.description = draft.description;
    form.value.welcome_message = draft.welcome_message;
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
  try {
    const bot = await botService.create({
      campaign_id: campaignId.value,
      telegram_account_id: accountId.value,
      target_url: targetUrl.value.trim(),
      display_name: form.value.display_name,
      username: form.value.username.replace(/^@/, ''),
      description: form.value.description,
      welcome_message: form.value.welcome_message,
      keyword: keyword.value || null,
      redirect_slug: redirectSlug.value,
      create_via_botfather: true,
      auto_start: autoStart.value,
    });
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
