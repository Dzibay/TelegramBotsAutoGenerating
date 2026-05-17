<template>
  <div v-if="loading" class="muted">Загрузка…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>
  <div v-else class="bot-edit">
    <header class="page-header">
      <RouterLink to="/app/bots" class="back">← Боты</RouterLink>
      <div class="title-row">
        <h1>@{{ bot.username || bot.id }}</h1>
        <StatusBadge :status="bot.status" />
      </div>
    </header>

    <form class="card form" @submit.prevent="onSave">
      <div class="form-group">
        <label>Имя</label>
        <input v-model="form.display_name" required maxlength="64" />
      </div>
      <div class="form-group">
        <label>Описание</label>
        <textarea v-model="form.description" rows="3" />
      </div>
      <div class="form-group">
        <label>Приветствие</label>
        <textarea v-model="form.welcome_message" rows="4" required />
      </div>
      <div class="form-group">
        <label>Ключевое слово</label>
        <input v-model="form.keyword" />
      </div>

      <p v-if="saveError" class="error-text">{{ saveError }}</p>
      <div class="actions">
        <button
          v-if="bot.status !== 'active'"
          type="button"
          :disabled="acting"
          @click="onStart"
        >
          Запустить
        </button>
        <button v-else type="button" class="btn-ghost" :disabled="acting" @click="onStop">
          Остановить
        </button>
        <button type="submit" :disabled="saving">{{ saving ? 'Сохранение…' : 'Сохранить' }}</button>
        <button type="button" class="btn-danger" :disabled="acting" @click="onDelete">Удалить</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import StatusBadge from '../components/StatusBadge.vue';
import { botService } from '../services/botService';

const route = useRoute();
const router = useRouter();
const bot = ref({});
const loading = ref(true);
const loadError = ref(null);
const saveError = ref(null);
const saving = ref(false);
const acting = ref(false);
const form = ref({
  display_name: '',
  description: '',
  welcome_message: '',
  keyword: '',
});

async function load() {
  loading.value = true;
  try {
    bot.value = await botService.get(Number(route.params.id));
    form.value = {
      display_name: bot.value.display_name,
      description: bot.value.description || '',
      welcome_message: bot.value.welcome_message || '',
      keyword: bot.value.keyword || '',
    };
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Бот не найден';
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  saveError.value = null;
  try {
    bot.value = await botService.update(bot.value.id, form.value);
  } catch (e) {
    saveError.value = e.response?.data?.error || 'Ошибка сохранения';
  } finally {
    saving.value = false;
  }
}

async function onStart() {
  acting.value = true;
  try {
    bot.value = await botService.start(bot.value.id);
  } catch (e) {
    saveError.value = e.response?.data?.error || 'Ошибка запуска';
  } finally {
    acting.value = false;
  }
}

async function onStop() {
  acting.value = true;
  try {
    bot.value = await botService.stop(bot.value.id);
  } catch (e) {
    saveError.value = e.response?.data?.error || 'Ошибка остановки';
  } finally {
    acting.value = false;
  }
}

async function onDelete() {
  if (!confirm('Удалить бота?')) return;
  acting.value = true;
  try {
    await botService.remove(bot.value.id);
    router.push({ name: 'bots-hub' });
  } catch (e) {
    saveError.value = e.response?.data?.error || 'Ошибка удаления';
  } finally {
    acting.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.bot-edit {
  max-width: 560px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.35rem;
}

.title-row h1 {
  margin: 0;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.35);
}
</style>
