<template>
  <div v-if="loading" class="muted">Загрузка…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>
  <div v-else class="edit-page">
    <header class="page-header">
      <RouterLink :to="{ name: 'campaign-detail', params: { id } }" class="back">← Кампания</RouterLink>
      <h1>Редактирование кампании</h1>
    </header>

    <form class="card form" @submit.prevent="onSave">
      <div class="form-group">
        <label>Название</label>
        <input v-model="title" required placeholder="Название группы аккаунтов" />
      </div>
      <div class="form-group">
        <label>Ссылка на рекламируемый сервис</label>
        <input v-model="resourceUrl" type="url" placeholder="https://..." />
        <p class="field-hint">Используется при массовом и ручном создании ботов</p>
      </div>

      <CampaignKeywordsEditor
        :campaign-id="id"
        :keywords="keywords"
        :niche-description="nicheDescription"
        @update:keywords="keywords = $event"
        @update:niche-description="nicheDescription = $event"
      />

      <p v-if="saveError" class="error-text">{{ saveError }}</p>
      <div class="actions">
        <RouterLink :to="{ name: 'campaign-detail', params: { id } }" class="btn-ghost">Отмена</RouterLink>
        <button type="submit" :disabled="saving">{{ saving ? 'Сохранение…' : 'Сохранить' }}</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import CampaignKeywordsEditor from '../components/CampaignKeywordsEditor.vue';
import { campaignService } from '../services/campaignService';

const route = useRoute();
const router = useRouter();
const id = computed(() => Number(route.params.id));
const loading = ref(true);
const loadError = ref(null);
const saveError = ref(null);
const saving = ref(false);
const title = ref('');
const resourceUrl = ref('');
const nicheDescription = ref('');
const keywords = ref([]);

async function load() {
  loading.value = true;
  try {
    const { campaign } = await campaignService.get(id.value);
    title.value = campaign.title;
    resourceUrl.value = campaign.resource_url || '';
    nicheDescription.value = campaign.niche_description || '';
    keywords.value = campaign.keywords || [];
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  saveError.value = null;
  try {
    await campaignService.update(id.value, {
      title: title.value.trim(),
      resource_url: resourceUrl.value.trim() || null,
      niche_description: nicheDescription.value.trim() || null,
      keywords: keywords.value,
    });
    router.push({ name: 'campaign-detail', params: { id: id.value } });
  } catch (e) {
    saveError.value = e.response?.data?.error || 'Ошибка сохранения';
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.edit-page {
  max-width: 640px;
}

.actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.actions button {
  flex: 1;
}

.field-hint {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}
</style>
