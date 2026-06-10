<template>
  <div v-if="loading" class="muted">Загрузка…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>
  <div v-else class="edit-page">
    <header class="page-header">
      <h1>Настройки кампании</h1>
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

      <div class="form-group">
        <label>Тематика (для AI, необязательно)</label>
        <textarea
          v-model="nicheDescription"
          rows="3"
          placeholder="Например: VPN и обход блокировок — помогает при генерации текстов"
        />
        <p class="field-hint">
          Ключевые фразы задаются при создании каждого бота, не здесь.
        </p>
      </div>

      <details class="defaults-block" open>
        <summary>Дефолтные тексты ботов</summary>
        <p class="field-hint block-hint">
          Подставляются при создании ботов, если поле пустое (вручную или после AI). Тексты сохраняются
          как вы их ввели — ссылку укажите в тексте сами, если она нужна.
        </p>
        <div class="form-group">
          <label>О себе в профиле (до 120 символов)</label>
          <textarea
            v-model="defaultAboutText"
            rows="2"
            maxlength="120"
            placeholder="Короткая строка в карточке бота"
          />
        </div>
        <div class="form-group">
          <label>Описание в чате до Start (до 512 символов)</label>
          <textarea
            v-model="defaultDescription"
            rows="4"
            maxlength="512"
            placeholder="Текст до нажатия кнопки Start"
          />
        </div>
        <div class="form-group">
          <label>Приветствие после Start (до 2000 символов)</label>
          <textarea
            v-model="defaultWelcomeMessage"
            rows="5"
            maxlength="2000"
            placeholder="Первое сообщение в чате"
          />
        </div>
      </details>

      <p v-if="saveError" class="error-text">{{ saveError }}</p>
      <div class="actions">
        <RouterLink :to="{ name: 'campaign-workspace', params: { id } }" class="btn-ghost">Отмена</RouterLink>
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
const title = ref('');
const resourceUrl = ref('');
const nicheDescription = ref('');
const defaultAboutText = ref('');
const defaultDescription = ref('');
const defaultWelcomeMessage = ref('');

async function load() {
  loading.value = true;
  try {
    const { campaign } = await campaignService.get(id.value);
    title.value = campaign.title;
    resourceUrl.value = campaign.resource_url || '';
    nicheDescription.value = campaign.niche_description || '';
    defaultAboutText.value = campaign.default_about_text || '';
    defaultDescription.value = campaign.default_description || '';
    defaultWelcomeMessage.value = campaign.default_welcome_message || '';
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
      default_about_text: defaultAboutText.value.trim() || null,
      default_description: defaultDescription.value.trim() || null,
      default_welcome_message: defaultWelcomeMessage.value.trim() || null,
    });
    router.push({ name: 'campaign-workspace', params: { id: id.value } });
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

.actions button {
  flex: 1;
}

.defaults-block {
  margin: 1rem 0;
  padding: 0.85rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: rgba(8, 12, 20, 0.4);
}

.block-hint {
  margin: 0 0 0.75rem;
}
</style>
