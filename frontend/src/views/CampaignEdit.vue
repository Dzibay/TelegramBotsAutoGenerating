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
        <input v-model="form.title" required />
      </div>
      <div class="form-group">
        <label>Ссылка на ресурс</label>
        <input v-model="form.resource_url" type="url" required />
      </div>
      <div class="form-group">
        <label>Описание ниши</label>
        <textarea v-model="form.niche_description" rows="3" />
      </div>
      <div class="form-group">
        <label>Ключевые слова (через запятую)</label>
        <input v-model="keywordsRaw" required />
      </div>
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
import { campaignService } from '../services/campaignService';

const route = useRoute();
const router = useRouter();
const id = computed(() => Number(route.params.id));
const loading = ref(true);
const loadError = ref(null);
const saveError = ref(null);
const saving = ref(false);
const keywordsRaw = ref('');
const form = ref({ title: '', resource_url: '', niche_description: '' });

async function load() {
  loading.value = true;
  try {
    const { campaign } = await campaignService.get(id.value);
    form.value = {
      title: campaign.title,
      resource_url: campaign.resource_url,
      niche_description: campaign.niche_description || '',
    };
    keywordsRaw.value = (campaign.keywords || []).join(', ');
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  saveError.value = null;
  const keywords = keywordsRaw.value
    .split(',')
    .map((k) => k.trim())
    .filter(Boolean);
  try {
    await campaignService.update(id.value, {
      title: form.value.title,
      resource_url: form.value.resource_url,
      niche_description: form.value.niche_description || null,
      keywords,
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
  max-width: 560px;
}

.actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.actions button {
  flex: 1;
}
</style>
