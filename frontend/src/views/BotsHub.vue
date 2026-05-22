<template>
  <div class="bots-hub">
    <header class="page-header">
      <div>
        <h1>Боты</h1>
        <p class="subtitle">Все боты в одном месте: запуск, остановка и редактирование</p>
      </div>
      <RouterLink to="/app/bots/new" class="btn">+ Создать бота</RouterLink>
    </header>

    <p v-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="error" class="error-text">{{ error }}</p>
    <p v-else-if="!campaigns.length" class="muted card empty">
      Ботов пока нет.
      <RouterLink to="/app/bots/new">Создайте первого</RouterLink>
    </p>

    <div v-else class="campaigns">
      <section v-for="camp in campaigns" :key="camp.campaign_id" class="card camp-block">
        <div class="camp-head">
          <RouterLink :to="{ name: 'campaign-detail', params: { id: camp.campaign_id } }">
            {{ camp.campaign_title }}
          </RouterLink>
        </div>
        <div v-for="acc in camp.accounts" :key="acc.telegram_account_id ?? 'none'" class="acc-block">
          <h3 class="acc-title">
            {{ acc.account_label || acc.account_phone || `Аккаунт #${acc.telegram_account_id}` }}
          </h3>
          <ul class="bot-rows">
            <li v-for="b in acc.bots" :key="b.id" class="bot-row">
              <div class="bot-info">
                <strong>@{{ b.username || '—' }}</strong>
                <span>{{ b.display_name }}</span>
                <span v-if="b.click_count != null" class="clicks">{{ b.click_count }} кликов</span>
                <a
                  v-if="botLink(b)"
                  :href="botLink(b)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="tg-open"
                  @click.stop
                >
                  Открыть в Telegram ↗
                </a>
              </div>
              <StatusBadge :status="b.status" />
              <div class="bot-actions">
                <button
                  v-if="b.status !== 'active'"
                  type="button"
                  class="btn btn-sm"
                  :disabled="actionId === b.id"
                  @click="onStart(b)"
                >
                  Запустить
                </button>
                <button
                  v-else
                  type="button"
                  class="btn btn-sm btn-ghost"
                  :disabled="actionId === b.id"
                  @click="onStop(b)"
                >
                  Остановить
                </button>
                <RouterLink :to="{ name: 'bot-edit', params: { id: b.id } }" class="btn btn-sm btn-ghost">
                  Изменить
                </RouterLink>
                <button
                  type="button"
                  class="btn btn-sm btn-danger"
                  :disabled="actionId === b.id"
                  @click="onDelete(b)"
                >
                  Удалить
                </button>
              </div>
            </li>
          </ul>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import StatusBadge from '../components/StatusBadge.vue';
import { botService } from '../services/botService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';

const taskStore = useAsyncTaskStore();
import { telegramBotUrl } from '../utils/botLink';

function botLink(b) {
  return b.telegram_url || telegramBotUrl(b.username);
}

const campaigns = ref([]);
const loading = ref(true);
const error = ref(null);
const actionId = ref(null);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    campaigns.value = await botService.listGrouped();
  } catch (e) {
    error.value = e.response?.data?.error || 'Не удалось загрузить ботов';
  } finally {
    loading.value = false;
  }
}

async function onStart(bot) {
  actionId.value = bot.id;
  try {
    await botService.start(bot.id);
    await load();
  } catch (e) {
    error.value = e.response?.data?.error || 'Ошибка запуска';
  } finally {
    actionId.value = null;
  }
}

async function onStop(bot) {
  actionId.value = bot.id;
  try {
    await botService.stop(bot.id);
    await load();
  } catch (e) {
    error.value = e.response?.data?.error || 'Ошибка остановки';
  } finally {
    actionId.value = null;
  }
}

async function onDelete(bot) {
  if (!confirm(`Удалить бота @${bot.username || bot.id}?`)) return;
  actionId.value = bot.id;
  try {
    await taskStore.run(
      'DELETE_BOT',
      () => botService.remove(bot.id),
      { username: bot.username || String(bot.id) }
    );
    await load();
  } catch (e) {
    error.value = e.response?.data?.error || 'Ошибка удаления';
  } finally {
    actionId.value = null;
  }
}

onMounted(load);
</script>

<style scoped>
.bots-hub {
  max-width: 960px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.page-header h1 {
  margin: 0;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

.empty {
  text-align: center;
  padding: 2rem;
}

.camp-block {
  margin-bottom: 1rem;
  padding: 1rem;
}

.camp-head {
  margin-bottom: 0.75rem;
  font-weight: 600;
}

.acc-block {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}

.acc-title {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  color: var(--muted);
}

.bot-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.bot-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
}

.bot-info {
  flex: 1;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.bot-info span {
  font-size: 0.8rem;
  color: var(--muted);
}

.tg-open {
  font-size: 0.75rem;
  color: var(--accent);
  margin-top: 0.15rem;
}

.clicks {
  font-size: 0.75rem;
  color: var(--muted);
}

.bot-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

</style>
