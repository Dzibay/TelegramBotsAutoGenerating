<template>
  <div v-if="loading" class="muted">Загрузка кампании…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>

  <div v-else class="detail">
    <header class="detail-header">
      <RouterLink to="/app" class="back">← Кампании</RouterLink>
      <div class="title-row">
        <h1>{{ campaign.title }}</h1>
        <StatusBadge :status="campaign.status" />
        <div class="header-btns">
          <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }" class="btn-ghost btn-sm">
            Изменить
          </RouterLink>
          <button type="button" class="btn-ghost btn-sm btn-danger" @click="onDeleteCampaign">
            Удалить
          </button>
        </div>
      </div>
      <p v-if="campaign.resource_url" class="resource">
        Сервис:
        <a :href="campaign.resource_url" target="_blank" rel="noopener noreferrer">{{ campaign.resource_url }}</a>
      </p>
      <p v-if="campaign.keywords?.length" class="keywords">
        Ключевые слова ({{ campaign.keywords.length }}):
        <span v-for="kw in campaign.keywords.slice(0, 8)" :key="kw" class="kw-chip">{{ kw }}</span>
        <span v-if="campaign.keywords.length > 8" class="kw-more">+{{ campaign.keywords.length - 8 }}</span>
      </p>
      <p v-else class="keywords warn-keywords">
        Нет ключевых слов —
        <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }">добавьте или сгенерируйте</RouterLink>
      </p>
    </header>

    <div class="stats">
      <div class="stat card">
        <span class="stat-val">{{ campaign.accounts_count }}</span>
        <span class="stat-label">аккаунтов</span>
      </div>
      <div class="stat card">
        <span class="stat-val">{{ campaign.bots_count }}</span>
        <span class="stat-label">ботов</span>
      </div>
      <div class="stat card">
        <span class="stat-val">{{ campaign.active_bots_count }}</span>
        <span class="stat-label">активных</span>
      </div>
    </div>

    <section v-if="job || canStart" class="progress-section card">
      <div class="progress-top">
        <h2>Массовое создание ботов</h2>
        <StatusBadge v-if="job" :status="job.status" />
        <StatusBadge v-else status="draft" />
      </div>
      <p v-if="job" class="progress-msg">{{ job.progress_message || '—' }}</p>
      <p v-else class="progress-msg muted">Ещё не запускали автоматическое создание</p>
      <div v-if="job && job.total_accounts" class="progress-bar-wrap">
        <div
          class="progress-bar"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
      <p v-if="job?.error_message" class="error-text">{{ job.error_message }}</p>
      <p v-if="!campaign.keywords?.length && canStart" class="warn-banner">
        Добавьте
        <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }">ключевые слова кампании</RouterLink>
        — каждый бот создаётся под своё слово.
      </p>
      <p v-if="!campaign.resource_url && canStart" class="warn-banner">
        Укажите
        <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }">ссылку на сервис</RouterLink>
        в настройках кампании.
      </p>
      <p v-if="readyAccountsCount === 0 && accounts.length && canStart" class="warn-banner">
        Нет готовых аккаунтов — нажмите «Проверить все» в блоке аккаунтов.
      </p>
      <div v-if="canStart" class="actions">
        <button
          type="button"
          :disabled="starting || !readyAccountsCount || !campaign.resource_url || !campaign.keywords?.length"
          @click="onStart"
        >
          {{ starting ? 'Запуск…' : 'Запустить создание ботов' }}
        </button>
      </div>
    </section>

    <div class="grid-2">
      <JobLogPanel :logs="logs" :loading="logsLoading" :polling="isPolling" />

      <div class="side">
        <CampaignAccountsPanel
          ref="accountsPanelRef"
          :accounts="accounts"
          :can-add="canAddAccounts"
          :attaching="attaching"
          :verifying-all="verifyingAll"
          :busy="accountBusy || taskStore.isActive"
          :busy-id="accountBusyId"
          :bots-busy-id="botsBusyId"
          :delete-busy="deleteBotBusy"
          :bots-lists="accountBotsLists"
          :bots-error="accountBotsErrors"
          :attach-message="attachMessage"
          @attach="onAttachPrepared"
          @verify="onVerifyAccount"
          @verify-all="onVerifyAllAccounts"
          @remove="onRemoveAccount"
          @load-bots="onLoadAccountBots"
          @delete-bot="onDeleteAccountBot"
        />

        <section class="card section">
          <div class="section-head">
            <h3>Боты</h3>
            <RouterLink
              :to="{ name: 'bot-create', query: { campaign_id: campaignId } }"
              class="btn btn-sm"
            >
              + Создать бота
            </RouterLink>
          </div>
          <p v-if="!bots.length" class="muted">Создайте бота вручную или запустите массовое создание</p>
          <ul v-else class="mini-list bots">
            <li v-for="b in bots" :key="b.id" class="bot-li">
              <div class="bot-li-main">
                <strong>@{{ b.username || '—' }}</strong>
                <span v-if="b.keyword" class="bot-kw" :title="'Ключевое слово'">«{{ b.keyword }}»</span>
                <span>{{ b.display_name }}</span>
                <span v-if="b.click_count != null" class="clicks">{{ b.click_count }} кл.</span>
                <StatusBadge :status="b.status" />
                <a
                  v-if="botLink(b)"
                  :href="botLink(b)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="tg-open"
                >
                  Telegram ↗
                </a>
              </div>
              <div class="bot-li-actions">
                <button
                  v-if="b.status !== 'active'"
                  type="button"
                  class="link-btn"
                  @click="onBotStart(b)"
                >
                  Запустить
                </button>
                <button v-else type="button" class="link-btn" @click="onBotStop(b)">Стоп</button>
                <RouterLink :to="{ name: 'bot-edit', params: { id: b.id } }" class="link-btn">
                  Изменить
                </RouterLink>
                <button type="button" class="link-btn danger" @click="onBotDelete(b)">Удалить</button>
              </div>
            </li>
          </ul>
          <RouterLink to="/app/bots" class="all-bots-link">Все боты →</RouterLink>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import CampaignAccountsPanel from '../components/CampaignAccountsPanel.vue';
import JobLogPanel from '../components/JobLogPanel.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { botService } from '../services/botService';
import { campaignService, jobService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { telegramBotUrl } from '../utils/botLink';

const taskStore = useAsyncTaskStore();

function accountLabel(account) {
  return account?.label || account?.phone || `Аккаунт #${account?.id}`;
}

function botLink(b) {
  return b.telegram_url || telegramBotUrl(b.username);
}

const route = useRoute();
const router = useRouter();
const campaignId = computed(() => Number(route.params.id));

const loading = ref(true);
const loadError = ref(null);
const campaign = ref({});
const accounts = ref([]);
const bots = ref([]);
const job = ref(null);
const logs = ref([]);
const logsLoading = ref(false);
const lastLogId = ref(0);
const starting = ref(false);
const attaching = ref(false);
const verifyingAll = ref(false);
const accountBusy = ref(false);
const accountBusyId = ref(null);
const botsBusyId = ref(null);
const deleteBotBusy = ref(null);
const accountBotsLists = ref({});
const accountBotsErrors = ref({});
const attachMessage = ref(null);
const accountsPanelRef = ref(null);
let pollTimer = null;

const readyAccountsCount = computed(
  () => accounts.value.filter((a) => a.status === 'ready' && a.can_create_bots).length
);

const isPolling = computed(
  () => job.value && ['queued', 'running'].includes(job.value.status)
);

const progressPercent = computed(() => {
  if (!job.value?.total_accounts) return 0;
  return Math.min(
    100,
    Math.round((job.value.processed_accounts / job.value.total_accounts) * 100)
  );
});

const canStart = computed(
  () =>
    campaign.value.accounts_count > 0 &&
    (!job.value || !['queued', 'running'].includes(job.value.status)) &&
    ['draft', 'failed', 'completed'].includes(campaign.value.status)
);

const canAddAccounts = computed(
  () => !job.value || !['running'].includes(job.value.status)
);

async function loadCampaign() {
  const data = await campaignService.get(campaignId.value);
  campaign.value = data.campaign;
  job.value = data.activeJob;
}

async function loadExtras() {
  const [acc, b] = await Promise.all([
    campaignService.getAccounts(campaignId.value),
    campaignService.getBots(campaignId.value),
  ]);
  accounts.value = acc;
  bots.value = b;
}

async function fetchLogs() {
  if (!job.value?.id) return;
  logsLoading.value = true;
  try {
    const batch = await jobService.getLogs(job.value.id, lastLogId.value);
    if (batch.length) {
      logs.value = [...logs.value, ...batch];
      lastLogId.value = batch[batch.length - 1].id;
    }
  } finally {
    logsLoading.value = false;
  }
}

async function refreshJob() {
  if (!job.value?.id) return;
  job.value = await jobService.get(job.value.id);
  if (!['queued', 'running'].includes(job.value.status)) {
    await loadCampaign();
    await loadExtras();
  }
}

async function poll() {
  await refreshJob();
  await fetchLogs();
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(poll, 2000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function onStart() {
  starting.value = true;
  try {
    job.value = await taskStore.run('START_CAMPAIGN', () =>
      campaignService.start(campaignId.value)
    );
    logs.value = [];
    lastLogId.value = 0;
    await fetchLogs();
    startPolling();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось запустить';
  } finally {
    starting.value = false;
  }
}

async function onDeleteCampaign() {
  if (!confirm(`Удалить кампанию «${campaign.value.title}»?`)) return;
  try {
    await campaignService.remove(campaignId.value);
    router.push({ name: 'dashboard' });
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка удаления';
  }
}

async function onBotStart(b) {
  try {
    await botService.start(b.id);
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка запуска';
  }
}

async function onBotStop(b) {
  try {
    await botService.stop(b.id);
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка остановки';
  }
}

async function onBotDelete(b) {
  if (!confirm(`Удалить @${b.username || b.id}?`)) return;
  try {
    await taskStore.run(
      'DELETE_BOT',
      () => botService.remove(b.id),
      { username: b.username || String(b.id) }
    );
    await loadCampaign();
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка удаления';
  }
}

async function onAttachPrepared(ids) {
  if (!ids?.length) return;
  attaching.value = true;
  attachMessage.value = null;
  loadError.value = null;
  try {
    const result = await taskStore.run(
      'ATTACH_ACCOUNTS',
      () => campaignService.attachPreparedAccounts(campaignId.value, ids),
      { count: ids.length }
    );
    accounts.value = result.accounts ?? [];
    const s = result.verifySummary;
    if (s) {
      attachMessage.value = `Добавлено и проверено: ${s.verified_ok} OK, ${s.verified_failed} с ошибкой`;
    }
    await loadCampaign();
    accountsPanelRef.value?.reloadPicker?.();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка добавения аккаунтов';
  } finally {
    attaching.value = false;
  }
}

async function onVerifyAccount(account) {
  accountBusy.value = true;
  accountBusyId.value = account.id;
  loadError.value = null;
  try {
    const updated = await taskStore.run(
      'VERIFY_ACCOUNT',
      () => campaignService.verifyAccount(campaignId.value, account.id),
      { accountId: account.id, accountLabel: accountLabel(account) }
    );
    const idx = accounts.value.findIndex((a) => a.id === account.id);
    if (idx >= 0) accounts.value[idx] = updated;
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка проверки';
  } finally {
    accountBusy.value = false;
    accountBusyId.value = null;
  }
}

async function onVerifyAllAccounts() {
  verifyingAll.value = true;
  loadError.value = null;
  try {
    const result = await taskStore.run(
      'VERIFY_ALL_ACCOUNTS',
      () => campaignService.verifyAllAccounts(campaignId.value),
      { count: accounts.value.length }
    );
    accounts.value = result.accounts ?? accounts.value;
    attachMessage.value = `Проверка: ${result.verified_ok} OK, ${result.verified_failed} ошибок`;
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка проверки';
  } finally {
    verifyingAll.value = false;
  }
}

function patchAccount(updated) {
  const idx = accounts.value.findIndex((a) => a.id === updated.id);
  if (idx >= 0) {
    accounts.value[idx] = { ...accounts.value[idx], ...updated };
  }
}

async function onLoadAccountBots(account) {
  botsBusyId.value = account.id;
  accountBotsErrors.value = { ...accountBotsErrors.value, [account.id]: null };
  try {
    const data = await taskStore.run(
      'LIST_ACCOUNT_BOTS',
      () => campaignService.listAccountBots(campaignId.value, account.id),
      { accountId: account.id, accountLabel: accountLabel(account) }
    );
    accountBotsLists.value = { ...accountBotsLists.value, [account.id]: data.bots ?? [] };
    const idx = accounts.value.findIndex((a) => a.id === account.id);
    if (idx >= 0) {
      accounts.value[idx] = {
        ...accounts.value[idx],
        bots_created: data.bots_created,
        bots_in_telegram: data.telegram_bots_count,
        bots_in_db: data.bots_in_app,
      };
    }
  } catch (err) {
    accountBotsErrors.value = {
      ...accountBotsErrors.value,
      [account.id]: err.response?.data?.error || 'Не удалось загрузить список ботов',
    };
  } finally {
    botsBusyId.value = null;
  }
}

async function onDeleteAccountBot({ account, bot }) {
  const uname = bot.username;
  if (!confirm(`Удалить @${uname} из Telegram${bot.in_app ? ' и из списка кампании' : ''}?`)) return;
  deleteBotBusy.value = `${account.id}:${uname}`;
  loadError.value = null;
  try {
    const data = await taskStore.run(
      'DELETE_ACCOUNT_BOT',
      async () => {
        const result = await campaignService.deleteAccountBot(
          campaignId.value,
          account.id,
          uname
        );
        const listData = await campaignService.listAccountBots(campaignId.value, account.id);
        accountBotsLists.value = {
          ...accountBotsLists.value,
          [account.id]: listData.bots ?? [],
        };
        return { ...result, listData };
      },
      {
        accountId: account.id,
        accountLabel: accountLabel(account),
        username: uname,
      }
    );
    patchAccount({
      id: account.id,
      bots_created: data.bots_created,
      bots_in_telegram: data.telegram_bots_count,
      bots_in_db: data.listData?.bots_in_app,
    });
    await loadCampaign();
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Не удалось удалить бота';
  } finally {
    deleteBotBusy.value = null;
  }
}

async function onRemoveAccount(account) {
  if (!confirm(`Убрать «${account.label || account.phone || account.id}» из кампании?`)) return;
  accountBusy.value = true;
  accountBusyId.value = account.id;
  try {
    await campaignService.removeAccount(campaignId.value, account.id);
    await loadCampaign();
    await loadExtras();
    accountsPanelRef.value?.reloadPicker?.();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Не удалось убрать аккаунт';
  } finally {
    accountBusy.value = false;
    accountBusyId.value = null;
  }
}

watch(isPolling, (v) => {
  if (v) startPolling();
  else stopPolling();
});

onMounted(async () => {
  try {
    await loadCampaign();
    await loadExtras();
    if (job.value?.id) {
      await fetchLogs();
      if (isPolling.value) startPolling();
    }
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  } finally {
    loading.value = false;
  }
});

onUnmounted(stopPolling);
</script>

<style scoped>
.detail-header {
  margin-bottom: 1.25rem;
}

.back {
  font-size: 0.875rem;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

.title-row h1 {
  margin: 0;
  font-size: 1.35rem;
}

.resource,
.keywords {
  margin: 0.35rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
}

.warn-keywords {
  color: #fbbf24;
}

.kw-chip {
  display: inline-block;
  margin: 0.15rem 0.25rem 0 0;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
  font-size: 0.75rem;
}

.kw-more {
  font-size: 0.75rem;
  opacity: 0.8;
}

.bot-kw {
  font-size: 0.75rem;
  color: var(--accent);
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.stat {
  text-align: center;
  padding: 1rem;
}

.stat-val {
  display: block;
  font-size: 1.5rem;
  font-weight: 700;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--muted);
}

.progress-section h2 {
  margin: 0;
  font-size: 1rem;
}

.progress-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.progress-msg {
  margin: 0 0 0.75rem;
  color: var(--muted);
  font-size: 0.9rem;
}

.progress-bar-wrap {
  height: 6px;
  background: var(--bg);
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s;
}

.progress-section {
  margin-bottom: 1.25rem;
}

.actions {
  margin-top: 1rem;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 800px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}

.section h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.mini-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.mini-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.875rem;
}

.mini-meta {
  width: 100%;
  font-size: 0.75rem;
  color: var(--muted);
}

.bots li {
  flex-direction: column;
  align-items: flex-start;
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

.upload-more {
  display: block;
  margin-top: 0.75rem;
  padding: 0.5rem;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--muted);
}

.side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.header-btns {
  display: flex;
  gap: 0.35rem;
  margin-left: auto;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.section-head h3 {
  margin: 0;
}

.bot-li {
  flex-direction: column;
  align-items: stretch !important;
  gap: 0.35rem;
}

.bot-li-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.tg-open {
  font-size: 0.75rem;
  color: var(--accent);
}

.clicks {
  font-size: 0.75rem;
  color: var(--muted);
}

.bot-li-actions {
  display: flex;
  gap: 0.5rem;
}

.warn-banner {
  margin: 0.5rem 0 0;
  padding: 0.6rem 0.75rem;
  font-size: 0.85rem;
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.35);
  border-radius: 8px;
  color: #fde047;
}

.warn-banner a {
  color: var(--accent);
}

</style>
