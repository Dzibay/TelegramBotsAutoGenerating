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

    <p v-if="justCreated" class="success-banner card">Бот создан. Откройте его в Telegram по ссылке ниже и отправьте /start.</p>

    <BotTelegramPanel
      :bot="bot"
      :auto-verify="justCreated"
      @verified="onVerified"
    />

    <form class="card form" @submit.prevent="onSave">
      <div class="form-group">
        <label>Ссылка на рекламируемый сервис</label>
        <input v-model="form.target_url" type="url" required placeholder="https://..." />
        <p class="field-hint">Сайт, на который ведёт ссылка из бота (при включённом счётчике переходов).</p>
      </div>

      <BotLinkModeField v-model="form.link_mode" :preview-url="linkPreview" />

      <BotProfileFields
        v-model="profile"
        username-readonly
        :keyword="form.keyword"
        :public-link="linkPreview"
        :avatar-url="avatarDisplayUrl"
        @update:avatar-file="pendingAvatarFile = $event"
      />

      <div class="form-group">
        <label>Ключевое слово</label>
        <input v-model="form.keyword" />
      </div>

      <label class="check">
        <input v-model="form.sync_botfather" type="checkbox" />
        Обновить в Telegram (имя, описание, аватар)
      </label>
      <label v-if="form.sync_botfather" class="check">
        <input v-model="form.generate_avatar" type="checkbox" />
        Перегенерировать аватар через AI
      </label>

      <p v-if="saveError" class="error-text">{{ saveError }}</p>
      <InlineTaskIndicator
        v-if="saving && form.sync_botfather"
        :username="bot.username"
        fallback-label="Обновляем профиль в Telegram…"
      />
      <InlineTaskIndicator
        v-if="acting"
        :username="bot.username"
        fallback-label="Операция с ботом…"
      />
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
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import BotProfileFields from '../components/BotProfileFields.vue';
import BotTelegramPanel from '../components/BotTelegramPanel.vue';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { botService } from '../services/botService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';

const taskStore = useAsyncTaskStore();

const route = useRoute();
const router = useRouter();
const justCreated = computed(() => route.query.created === '1');
const bot = ref({});
const loading = ref(true);
const loadError = ref(null);
const saveError = ref(null);
const saving = ref(false);
const acting = ref(false);
const pendingAvatarFile = ref(null);

const form = ref({
  target_url: '',
  link_mode: 'redirect',
  keyword: '',
  sync_botfather: false,
  generate_avatar: false,
});

const profile = ref({
  display_name: '',
  username: '',
  description: '',
  about_text: '',
  welcome_message: '',
  welcome_button_enabled: true,
  welcome_button_text: 'Перейти по ссылке',
});

const avatarDisplayUrl = computed(() => {
  if (pendingAvatarFile.value || !bot.value?.has_avatar) return null;
  return botService.avatarUrl(bot.value);
});

const linkPreview = computed(() => {
  if (form.value.link_mode === 'direct') return form.value.target_url?.trim() || '';
  return bot.value.public_link || bot.value.tracking_url || '';
});

async function load() {
  loading.value = true;
  try {
    bot.value = await botService.get(Number(route.params.id));
    form.value = {
      target_url: bot.value.target_url || '',
      link_mode: bot.value.link_mode || 'redirect',
      keyword: bot.value.keyword || '',
      sync_botfather: false,
      generate_avatar: false,
    };
    profile.value = {
      display_name: bot.value.display_name,
      username: bot.value.username || '',
      description: bot.value.description || '',
      about_text: bot.value.about_text || '',
      welcome_message: bot.value.welcome_message || '',
      welcome_button_enabled: bot.value.welcome_button_enabled !== false,
      welcome_button_text: bot.value.welcome_button_text || 'Перейти по ссылке',
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
  const syncBf = form.value.sync_botfather;
  try {
    const runUpdate = async () => {
      if (pendingAvatarFile.value) {
        bot.value = await botService.uploadAvatar(bot.value.id, pendingAvatarFile.value);
        pendingAvatarFile.value = null;
      }
      bot.value = await botService.update(bot.value.id, {
        target_url: form.value.target_url,
        link_mode: form.value.link_mode,
        display_name: profile.value.display_name,
        description: profile.value.description,
        about_text: profile.value.about_text,
        welcome_message: profile.value.welcome_message,
        welcome_button_enabled: profile.value.welcome_button_enabled,
        welcome_button_text: profile.value.welcome_button_text,
        keyword: form.value.keyword,
        sync_botfather: syncBf,
        generate_avatar: form.value.generate_avatar,
      });
    };
    if (syncBf) {
      await taskStore.run('SYNC_BOTFATHER', runUpdate, {
        username: bot.value.username,
      });
    } else {
      await runUpdate();
    }
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

function onVerified(result) {
  if (result?.username) {
    bot.value = { ...bot.value, username: result.username, telegram_url: result.telegram_url };
  }
}

async function onDelete() {
  if (!confirm('Удалить бота?')) return;
  acting.value = true;
  try {
    await taskStore.run(
      'DELETE_BOT',
      () => botService.remove(bot.value.id),
      { username: bot.value.username }
    );
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

.success-banner {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #86efac;
  font-size: 0.9rem;
}

.field-hint {
  font-size: 0.8rem;
  color: var(--muted);
  margin-top: 0.35rem;
}

.check {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0.5rem 0;
  font-size: 0.9rem;
  cursor: pointer;
}

.check input {
  width: auto;
}
</style>
