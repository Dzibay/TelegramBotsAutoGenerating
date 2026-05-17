<template>
  <div>
    <header class="dash-header">
      <div>
        <h1>Кампании</h1>
        <p class="subtitle">Группы аккаунтов и ботов</p>
      </div>
      <div class="header-actions">
        <RouterLink to="/app/accounts/prepare" class="btn-ghost">Подготовка</RouterLink>
        <RouterLink to="/app/bots" class="btn-ghost">Боты</RouterLink>
        <RouterLink to="/app/campaigns/new" class="btn">+ Кампания</RouterLink>
      </div>
    </header>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>
    <p v-else-if="loading" class="muted">Загрузка…</p>
    <p v-else-if="!campaigns.length" class="muted card empty">
      Пока нет кампаний.
      <RouterLink to="/app/campaigns/new">Создайте первую</RouterLink>
    </p>

    <ul v-else class="list">
      <li v-for="c in campaigns" :key="c.id" class="card item">
        <RouterLink :to="{ name: 'campaign-detail', params: { id: c.id } }" class="item-link">
          <div class="item-main">
            <div class="item-title">
              <strong>{{ c.title }}</strong>
              <StatusBadge :status="c.status" />
            </div>
            <p class="meta">
              {{ c.bots_count }} ботов · {{ c.accounts_count }} аккаунтов
              <span v-if="c.active_bots_count"> · {{ c.active_bots_count }} активных</span>
            </p>
          </div>
          <span class="chevron">→</span>
        </RouterLink>
        <div class="item-actions" @click.stop>
          <RouterLink :to="{ name: 'campaign-edit', params: { id: c.id } }" class="btn-ghost btn-xs">
            Изменить
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

const router = useRouter();
const campaigns = ref([]);
const loading = ref(true);
const loadError = ref(null);

async function onDelete(c) {
  if (!confirm(`Удалить кампанию «${c.title}»?`)) return;
  try {
    await campaignService.remove(c.id);
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
  margin-bottom: 1.5rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

.dash-header h1 {
  margin: 0;
  font-size: 1.35rem;
}

.subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
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
  padding: 1rem;
  text-decoration: none;
  color: inherit;
}

.item-link:hover {
  text-decoration: none;
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

.desc {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
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
