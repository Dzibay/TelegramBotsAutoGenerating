<template>
  <section class="profile-fields">
    <h3 v-if="showTitle" class="section-title">Профиль бота в Telegram</h3>

    <div class="form-group avatar-block">
      <label>Аватар</label>
      <div class="avatar-row">
        <div class="avatar-preview">
          <img v-if="avatarPreviewUrl" :src="avatarPreviewUrl" alt="Аватар" />
          <span v-else class="avatar-placeholder">?</span>
        </div>
        <div class="avatar-actions">
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            class="file-input"
            @change="onFileChange"
          />
          <button type="button" class="btn-ghost btn-sm" @click="fileInput?.click()">
            Загрузить файл
          </button>
          <button
            type="button"
            class="btn-ghost btn-sm"
            :disabled="generatingAvatar || !canGenerateAvatar"
            @click="onGenerateAvatar"
          >
            {{ generatingAvatar ? 'Генерация…' : '✨ AI-аватар' }}
          </button>
          <button
            v-if="avatarPreviewUrl"
            type="button"
            class="btn-ghost btn-sm"
            @click="clearAvatar"
          >
            Убрать
          </button>
        </div>
      </div>
      <label v-if="showGenerateOnCreate" class="checkbox-row">
        <input v-model="generateAvatarLocal" type="checkbox" />
        Сгенерировать AI-аватар при создании, если файл не выбран
      </label>
      <p class="field-hint">JPG/PNG/WebP до 5 МБ. Показывается в карточке бота.</p>
    </div>

    <div class="form-group">
      <label>Имя бота</label>
      <input
        :value="modelValue.display_name"
        required
        maxlength="64"
        placeholder="Например: VPN Помощник"
        @input="patch('display_name', $event.target.value)"
      />
      <p class="field-hint">Отображаемое имя в Telegram (до 64 символов).</p>
    </div>

    <div class="form-group">
      <label>Username (@)</label>
      <input
        :value="modelValue.username"
        :readonly="usernameReadonly"
        required
        maxlength="64"
        placeholder="my_service_bot"
        @input="patch('username', $event.target.value.replace(/^@/, ''))"
      />
      <p class="field-hint">
        <template v-if="usernameReadonly">Username задаётся при создании и не меняется.</template>
        <template v-else>
          Латиница, окончание <code>bot</code>. Кириллица будет транслитерирована.
        </template>
      </p>
    </div>

    <div class="form-group">
      <label>Короткое описание в профиле</label>
      <textarea
        :value="modelValue.about_text"
        rows="2"
        maxlength="120"
        placeholder="Текст под именем бота, до открытия чата"
        @input="patch('about_text', $event.target.value)"
      />
      <p class="field-hint">
        До 120 символов. Видно в профиле бота до начала диалога. Если пусто — подставится шаблон при создании.
      </p>
    </div>

    <div class="form-group">
      <label>Описание в чате</label>
      <textarea
        :value="modelValue.description"
        rows="4"
        maxlength="512"
        placeholder="Текст в пустом чате с ботом, до нажатия Start"
        @input="patch('description', $event.target.value)"
      />
      <p class="field-hint">
        До 512 символов. Показывается в пустом чате до кнопки «Старт». Можно заполнить кнопкой «Заполнить тексты автоматически».
      </p>
    </div>

    <div class="form-group">
      <label>Приветствие после «Старт»</label>
      <textarea
        :value="modelValue.welcome_message"
        rows="5"
        required
        maxlength="2000"
        placeholder="Первое сообщение после нажатия Start"
        @input="patch('welcome_message', $event.target.value)"
      />
    </div>

    <label class="checkbox-row">
      <input
        type="checkbox"
        :checked="modelValue.welcome_button_enabled !== false"
        @change="patch('welcome_button_enabled', $event.target.checked)"
      />
      Кнопка со ссылкой на сервис под сообщением
    </label>
    <div v-if="modelValue.welcome_button_enabled !== false" class="form-group button-text-group">
      <label>Текст кнопки</label>
      <input
        :value="modelValue.welcome_button_text || 'Перейти по ссылке'"
        type="text"
        maxlength="64"
        placeholder="Перейти по ссылке"
        @input="patch('welcome_button_text', $event.target.value)"
      />
      <p v-if="publicLink" class="field-hint">
        Ссылка кнопки: <code>{{ publicLink }}</code>
        (со счётчиком или прямая — как выбрано выше).
      </p>
      <p v-else class="field-hint">
        Ссылка кнопки — публичная ссылка бота (появится после генерации или создания).
      </p>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import apiClient from '../utils/apiClient';

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
  showTitle: { type: Boolean, default: true },
  usernameReadonly: { type: Boolean, default: false },
  showGenerateOnCreate: { type: Boolean, default: false },
  generateAvatar: { type: Boolean, default: true },
  avatarUrl: { type: String, default: null },
  keyword: { type: String, default: '' },
  avatarPrompt: { type: String, default: '' },
  publicLink: { type: String, default: '' },
});

const emit = defineEmits([
  'update:modelValue',
  'update:generateAvatar',
  'update:avatarFile',
  'update:avatarPreview',
]);

const fileInput = ref(null);
const avatarFile = ref(null);
const avatarObjectUrl = ref(null);
const generatingAvatar = ref(false);

const generateAvatarLocal = computed({
  get: () => props.generateAvatar,
  set: (v) => emit('update:generateAvatar', v),
});

const canGenerateAvatar = computed(() => props.keyword || props.avatarPrompt || props.modelValue.display_name);

const avatarPreviewUrl = computed(() => avatarObjectUrl.value || props.avatarUrl || null);

function patch(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value });
}

function onFileChange(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) {
    alert('Файл больше 5 МБ');
    return;
  }
  if (avatarObjectUrl.value) URL.revokeObjectURL(avatarObjectUrl.value);
  avatarFile.value = file;
  avatarObjectUrl.value = URL.createObjectURL(file);
  emit('update:avatarFile', file);
  emit('update:avatarPreview', avatarObjectUrl.value);
}

function clearAvatar() {
  if (avatarObjectUrl.value) URL.revokeObjectURL(avatarObjectUrl.value);
  avatarFile.value = null;
  avatarObjectUrl.value = null;
  if (fileInput.value) fileInput.value.value = '';
  emit('update:avatarFile', null);
  emit('update:avatarPreview', null);
}

async function onGenerateAvatar() {
  generatingAvatar.value = true;
  try {
    const res = await apiClient.post(
      '/bots/generate-avatar-preview',
      {
        prompt: props.avatarPrompt || null,
        keyword: props.keyword || props.modelValue.display_name || null,
      },
      { responseType: 'blob' }
    );
    const blob = res.data;
    const file = new File([blob], 'avatar.jpg', { type: 'image/jpeg' });
    if (avatarObjectUrl.value) URL.revokeObjectURL(avatarObjectUrl.value);
    avatarFile.value = file;
    avatarObjectUrl.value = URL.createObjectURL(blob);
    emit('update:avatarFile', file);
    emit('update:avatarPreview', avatarObjectUrl.value);
  } catch (e) {
    alert(e.response?.data?.error || 'Не удалось сгенерировать аватар');
  } finally {
    generatingAvatar.value = false;
  }
}

async function loadAvatarFromApi(url) {
  if (!url || avatarFile.value) return;
  try {
    const path = url.includes('/api/v1') ? url.split('/api/v1')[1] : url;
    const res = await apiClient.get(path, { responseType: 'blob' });
    if (avatarObjectUrl.value) URL.revokeObjectURL(avatarObjectUrl.value);
    avatarObjectUrl.value = URL.createObjectURL(res.data);
  } catch {
    /* ignore */
  }
}

watch(
  () => props.avatarUrl,
  (url) => {
    if (url) loadAvatarFromApi(url);
  },
  { immediate: true }
);

defineExpose({ avatarFile, clearAvatar });
</script>

<style scoped>
.profile-fields {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.section-title {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  font-weight: 600;
}

.avatar-row {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.avatar-preview {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--bg);
  border: 1px solid var(--border);
  flex-shrink: 0;
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--muted);
  font-size: 1.5rem;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.file-input {
  display: none;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.5rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.checkbox-row input {
  width: auto;
}

.button-text-group {
  margin-top: 0.35rem;
}

.button-text-group code {
  word-break: break-all;
  font-size: 0.75rem;
}
</style>
