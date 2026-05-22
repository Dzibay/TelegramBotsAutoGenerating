<template>
  <div>
    <header class="dash-header">
      <div>
        <h1>Шаг 1 — Кампания</h1>
        <p class="subtitle">Создайте группу для аккаунтов и ботов. Ключевые фразы задаются при создании каждого бота.</p>
      </div>
      <RouterLink to="/app/campaigns/new" class="btn">+ Новая кампания</RouterLink>
    </header>

    <ol class="steps-guide card">
      <li :class="{ done: campaigns.length }">
        <strong>Кампания</strong> — название и ссылка на ваш сервис
      </li>
      <li>
        <strong>Аккаунты</strong> —
        <RouterLink to="/app/accounts/prepare">подготовьте Telegram</RouterLink>
        и добавьте в кампанию
      </li>
      <li>
        <strong>Боты</strong> — по одному или списком: у каждого бота своя ключевая фраза
      </li>
    </ol>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>
    <p v-else-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="!campaigns.length" class="muted card empty">
      Пока нет кампаний.
      <RouterLink to="/app/campaigns/new">Создайте первую</RouterLink>
      — это займёт минуту.
    </p>

    <ul v-else class="list">
      <li v-for="c in campaigns" :key="c.id" class="card item">
        <button type="button" class="item-link" @click="openCampaign(c)">
          <div class="item-main">
            <div class="item-title">
              <strong>{{ c.title }}</strong>
              <StatusBadge :status="c.status" />
            </div>
            <p class="meta">
              {{ c.bots_count }} ботов · {{ c.accounts_count }} аккаунтов
            </p>
          </div>
          <span class="chevron">→</span>
        </button>
        <div class="item-actions">
          <button type="button" class="btn-ghost btn-xs" @click="openCampaign(c)">Открыть</button>
          <RouterLink :to="{ name: 'campaign-edit', params: { id: c.id } }" class="btn-ghost btn-xs">
            Настройки
          </RouterLink>
          <button type="button" class="btn-ghost btn-xs danger" @click="onDelete(c)">Удалить</button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import StatusBadge from '../components/StatusBadge.vue';
import { campaignService } from '../services/campaignService';
import { useWorkflowStore } from '../stores/workflowStore';

const router = useRouter();
const workflow = useWorkflowStore();
const campaigns = ref([]);
const loading = ref(true);
const loadError = ref(null);

function openCampaign(c) {
  workflow.setCampaign(c.id, c.title);
  router.push({ name: 'campaign-workspace', params: { id: c.id }, query: { tab: 'guide' } });
}

async function onDelete(c) {
  if (!confirm(`Удалить кампанию «${c.title}»?`)) return;
  try {
    await campaignService.remove(c.id);
    if (workflow.activeCampaignId === c.id) workflow.setCampaign(null);
    await load();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Ошибка удаления';
  }
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    campaigns.value = await campaignService.list();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось загрузить кампании';
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.dash-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.dash-header h1 {
  margin: 0;
  font-size: 1.35rem;
}

.subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
  max-width: 32rem;
}

.steps-guide {
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
  font-size: 0.88rem;
  color: var(--muted);
  line-height: 1.6;
}

.steps-guide li {
  margin: 0.35rem 0;
}

.steps-guide li.done {
  color: #86efac;
}

.empty {
  text-align: center;
  padding: 2rem;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.item {
  padding: 0;
  overflow: hidden;
}

.item-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 1rem;
  border: none;
  background: transparent;
  text-align: left;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.item-actions {
  display: flex;
  gap: 0.5rem;
  padding: 0 1rem 0.75rem;
  border-top: 1px solid var(--border);
  padding-top: 0.5rem;
}

.item-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.meta {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.chevron {
  color: var(--muted);
  font-size: 1.25rem;
}
</style>
