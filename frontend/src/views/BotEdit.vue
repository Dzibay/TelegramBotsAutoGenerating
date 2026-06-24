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

    <BotTelegramSyncStatus
      v-if="!(justCreated && (bot.telegram_sync_status || 'idle') === 'synced')"
      :status="bot.telegram_sync_status || 'idle'"
      :error="bot.telegram_sync_error || ''"
      :synced-at="bot.telegram_sync_at || ''"
    />

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
        :has-description-picture="bot.has_description_picture"
        :description-picture-cache-key="bot.updated_at"
        :avatar-cache-key="bot.updated_at"
        collapse-long-fields
        @update:avatar-file="pendingAvatarFile = $event"
        @update:avatar-preview="avatarPreviewUrl = $event"
        @update:description-picture-file="pendingDescriptionPictureFile = $event"
        @update:description-picture-preview="descriptionPicturePreviewUrl = $event"
      />

      <div class="form-group">
        <label>Ключевая фраза <span class="optional">(необязательно)</span></label>
        <input v-model="form.keyword" placeholder="Только для повторной AI-генерации" />
      </div>

      <label class="check">
        <input v-model="form.sync_botfather" type="checkbox" />
        Обновить в Telegram (имя, описание, аватар, картинка плаката)
      </label>
      <label v-if="form.sync_botfather" class="check">
        <input v-model="form.generate_avatar" type="checkbox" />
        Перегенерировать аватар через AI
      </label>

      <p v-if="saveNotice && !isSyncInProgress" class="success-banner card">{{ saveNotice }}</p>
      <p v-if="saveError" class="error-text">{{ saveError }}</p>
      <OperationStatus
        v-if="saving && form.sync_botfather"
        :message="taskStore.serverProgressMessage"
        :status="taskStore.serverJobStatus"
      />
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
      :description-picture-preview-url="descriptionPicturePreviewUrl"
      :bot-id="bot.id"
      :has-avatar="bot.has_avatar"
      :has-description-picture="bot.has_description_picture"
      :description-picture-cache-key="bot.updated_at"
      :avatar-cache-key="bot.updated_at"
      :public-link="linkPreview"
    />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BotAvatar from '../components/BotAvatar.vue';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import BotProfileFields from '../components/BotProfileFields.vue';
import BotTelegramPanel from '../components/BotTelegramPanel.vue';
import BotTelegramPreview from '../components/BotTelegramPreview.vue';
import BotTelegramSyncStatus from '../components/BotTelegramSyncStatus.vue';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import OperationStatus from '../components/OperationStatus.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { botService } from '../services/botService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { copyBotExportToClipboard } from '../utils/botExport';
import { formatApiError } from '../utils/apiErrorMessage';
import { isTelegramSyncInProgress } from '../utils/telegramSyncStatus';
import { pollBotTelegramSync } from '../utils/serverTaskProgress';
import { newIdempotencyKey } from '../utils/apiClient';

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
const descriptionPicturePreviewUrl = ref(null);
const loadError = ref(null);
const saveError = ref(null);
const saveNotice = ref(null);
const saving = ref(false);
const acting = ref(false);
const pendingAvatarFile = ref(null);
const pendingDescriptionPictureFile = ref(null);
const copiedExport = ref(false);
const syncPollTimer = ref(null);

const isSyncInProgress = computed(() =>
  isTelegramSyncInProgress(bot.value?.telegram_sync_status)
);

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

async function loadDescriptionPicturePreview(source) {
  if (descriptionPicturePreviewUrl.value?.startsWith('blob:')) {
    URL.revokeObjectURL(descriptionPicturePreviewUrl.value);
  }
  descriptionPicturePreviewUrl.value = null;
  if (source?.has_description_picture && source?.id) {
    try {
      descriptionPicturePreviewUrl.value = await botService.loadDescriptionPictureObjectUrl(
        source.id,
        source.updated_at
      );
    } catch {
      descriptionPicturePreviewUrl.value = null;
    }
  }
}

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
  loadDescriptionPicturePreview(source);
}

async function load() {
  loading.value = true;
  try {
    bot.value = await botService.get(Number(route.params.id));
    applyBotToForm(bot.value);
    syncSyncPoll();
  } catch (e) {
    loadError.value = formatApiError(e, 'Бот не найден');
  } finally {
    loading.value = false;
  }
}

async function refreshBotStatus() {
  if (!bot.value?.id) return;
  try {
    bot.value = await botService.get(bot.value.id);
  } catch {
    /* polling — не мешаем редактированию */
  }
}

function stopSyncPoll() {
  if (syncPollTimer.value) {
    clearInterval(syncPollTimer.value);
    syncPollTimer.value = null;
  }
}

function syncSyncPoll() {
  stopSyncPoll();
  if (isTelegramSyncInProgress(bot.value?.telegram_sync_status)) {
    syncPollTimer.value = setInterval(refreshBotStatus, 3000);
  }
}

watch(
  () => bot.value?.telegram_sync_status,
  () => syncSyncPoll()
);

async function onSave() {
  saving.value = true;
  saveError.value = null;
  saveNotice.value = null;
  const syncBf = form.value.sync_botfather;
  try {
    const runUpdate = async ({ logStep, setServerProgress } = {}) => {
      let forceAvatarSync = false;
      let forceDescriptionPictureSync = false;
      if (pendingAvatarFile.value) {
        const avatarResult = await botService.uploadAvatar(bot.value.id, pendingAvatarFile.value);
        bot.value = avatarResult.bot;
        pendingAvatarFile.value = null;
        forceAvatarSync = syncBf;
      }
      if (pendingDescriptionPictureFile.value) {
        const posterResult = await botService.uploadDescriptionPicture(
          bot.value.id,
          pendingDescriptionPictureFile.value
        );
        bot.value = posterResult.bot;
        pendingDescriptionPictureFile.value = null;
        forceDescriptionPictureSync = syncBf;
      }
      const idempotencyKey = newIdempotencyKey();
      const result = await botService.update(
        bot.value.id,
        {
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
          force_avatar_sync: forceAvatarSync,
          force_description_picture_sync: forceDescriptionPictureSync,
        },
        { idempotencyKey }
      );
      bot.value = result.bot;
      applyBotToForm(bot.value);
      form.value.sync_botfather = false;
      form.value.generate_avatar = false;
      if (result.telegramSyncPending || isTelegramSyncInProgress(bot.value.telegram_sync_status)) {
        saveNotice.value = null;
        logStep?.('Синхронизация с Telegram поставлена в очередь…', 'info');
        bot.value = await pollBotTelegramSync(bot.value.id, {
          onProgress: (msg, st) => setServerProgress?.(msg, st),
        });
        applyBotToForm(bot.value);
        saveNotice.value = result.message || 'Изменения сохранены и синхронизированы с Telegram.';
      } else if (result.message) {
        saveNotice.value = result.message;
      } else {
        saveNotice.value = 'Изменения сохранены.';
      }
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
onUnmounted(stopSyncPoll);
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
