<template>
  <div v-if="loading" class="muted">Загрузка…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>
  <div v-else class="bot-edit">
    <header class="page-header">
      <div class="title-row">
        <BotAvatar
          v-if="bot.id"
          :bot="bot"
          :size="48"
          class="title-avatar"
        />
        <h1>@{{ bot.username || bot.id }}</h1>
        <StatusBadge :status="bot.status" />
        <button
          type="button"
          class="btn btn-sm btn-ghost export-btn"
          @click="onCopyExport"
        >
          {{ copiedExport ? 'Скопировано' : 'Копировать данные' }}
        </button>
      </div>
    </header>

    <p v-if="justCreated" class="success-banner card">Бот создан. Откройте его в Telegram и отправьте /start.</p>

    <BotTelegramPanel
      :bot="bot"
      :auto-verify="justCreated"
      @verified="onVerified"
    />

    <div class="form-with-preview">
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
        :bot-id="bot.id"
        :has-avatar="bot.has_avatar"
        :avatar-cache-key="bot.updated_at"
        collapse-long-fields
        @update:avatar-file="pendingAvatarFile = $event"
        @update:avatar-preview="avatarPreviewUrl = $event"
      />

      <div class="form-group">
        <label>Ключевая фраза <span class="optional">(необязательно)</span></label>
        <input v-model="form.keyword" placeholder="Только для повторной AI-генерации" />
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

    <BotTelegramPreview
      :display-name="profile.display_name"
      :username="profile.username"
      :about-text="profile.about_text"
      :description="profile.description"
      :welcome-message="profile.welcome_message"
      :welcome-button-enabled="profile.welcome_button_enabled"
      :welcome-button-text="profile.welcome_button_text"
      :avatar-preview-url="avatarPreviewUrl"
      :bot-id="bot.id"
      :has-avatar="bot.has_avatar"
      :avatar-cache-key="bot.updated_at"
      :public-link="linkPreview"
    />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BotAvatar from '../components/BotAvatar.vue';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import BotProfileFields from '../components/BotProfileFields.vue';
import BotTelegramPanel from '../components/BotTelegramPanel.vue';
import BotTelegramPreview from '../components/BotTelegramPreview.vue';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { botService } from '../services/botService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { copyBotExportToClipboard } from '../utils/botExport';
import { formatApiError } from '../utils/apiErrorMessage';

const taskStore = useAsyncTaskStore();

const route = useRoute();
const router = useRouter();
const justCreated = computed(() => route.query.created === '1');
const bot = ref({});

const backRoute = computed(() => {
  const cid = bot.value?.campaign_id;
  if (cid) {
    return {
      name: 'campaign-workspace',
      params: { id: cid },
      query: { tab: 'list' },
    };
  }
  return { name: 'dashboard' };
});

const loading = ref(true);
const avatarPreviewUrl = ref(null);
const loadError = ref(null);
const saveError = ref(null);
const saving = ref(false);
const acting = ref(false);
const pendingAvatarFile = ref(null);
const copiedExport = ref(false);

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

const linkPreview = computed(() => {
  if (form.value.link_mode === 'direct') return form.value.target_url?.trim() || '';
  return bot.value.public_link || bot.value.tracking_url || '';
});

function applyBotToForm(source) {
  if (!source?.id) return;
  form.value = {
    target_url: source.target_url || '',
    link_mode: source.link_mode || 'redirect',
    keyword: source.keyword || '',
    sync_botfather: false,
    generate_avatar: false,
  };
  profile.value = {
    display_name: source.display_name,
    username: source.username || '',
    description: source.description || '',
    about_text: source.about_text || '',
    welcome_message: source.welcome_message || '',
    welcome_button_enabled: source.welcome_button_enabled !== false,
    welcome_button_text: source.welcome_button_text || 'Перейти по ссылке',
  };
}

async function load() {
  loading.value = true;
  try {
    bot.value = await botService.get(Number(route.params.id));
    applyBotToForm(bot.value);
  } catch (e) {
    loadError.value = formatApiError(e, 'Бот не найден');
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
      applyBotToForm(bot.value);
      form.value.sync_botfather = false;
      form.value.generate_avatar = false;
    };
    if (syncBf) {
      await taskStore.run('SYNC_BOTFATHER', runUpdate, {
        username: bot.value.username,
      });
    } else {
      await runUpdate();
    }
  } catch (e) {
    saveError.value = formatApiError(e, 'Ошибка сохранения');
  } finally {
    saving.value = false;
  }
}

async function onStart() {
  acting.value = true;
  try {
    bot.value = await botService.start(bot.value.id);
  } catch (e) {
    saveError.value = formatApiError(e, 'Ошибка запуска');
  } finally {
    acting.value = false;
  }
}

async function onStop() {
  acting.value = true;
  try {
    bot.value = await botService.stop(bot.value.id);
  } catch (e) {
    saveError.value = formatApiError(e, 'Ошибка остановки');
  } finally {
    acting.value = false;
  }
}

function onVerified(result) {
  if (result?.username) {
    bot.value = { ...bot.value, username: result.username, telegram_url: result.telegram_url };
  }
}

async function onCopyExport() {
  try {
    await copyBotExportToClipboard(profile.value);
    copiedExport.value = true;
    setTimeout(() => {
      copiedExport.value = false;
    }, 2000);
  } catch {
    saveError.value = 'Не удалось скопировать в буфер обмена';
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
    router.push(backRoute.value);
  } catch (e) {
    saveError.value = formatApiError(e, 'Ошибка удаления');
  } finally {
    acting.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.bot-edit {
  max-width: 1100px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.export-btn {
  margin-left: auto;
}
</style>
