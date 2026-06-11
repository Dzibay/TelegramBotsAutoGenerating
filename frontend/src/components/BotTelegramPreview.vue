<template>
  <aside class="tg-preview" aria-label="Предпросмотр бота в Telegram">
    <div class="tg-preview-head">
      <h3 class="tg-preview-title">Как в Telegram</h3>
      <div class="tg-tabs" role="tablist">
        <button
          v-for="t in tabs"
          :key="t.id"
          type="button"
          role="tab"
          class="tg-tab"
          :class="{ active: activeTab === t.id }"
          :aria-selected="activeTab === t.id"
          @click="activeTab = t.id"
        >
          {{ t.label }}
        </button>
      </div>
      <p class="tg-map muted">
        <template v-if="activeTab === 'profile'">Поле: «О себе в профиле» + @username</template>
        <template v-else-if="activeTab === 'prestart'">Поле: «Описание в чате» (до Start)</template>
        <template v-else>Поле: «Приветствие» + кнопка со ссылкой</template>
      </p>
    </div>

    <div class="tg-phone">
      <!-- 1. Страница профиля бота (Info) -->
      <div v-show="activeTab === 'profile'" class="tg-screen tg-screen--profile">
        <div class="tg-modal">
          <span class="tg-modal-close" aria-hidden="true">×</span>
          <div class="tg-profile-top">
            <div class="tg-avatar-lg">
              <img v-if="resolvedPreviewUrl" :src="resolvedPreviewUrl" alt="" />
              <BotAvatar
                v-else-if="showServerAvatar"
                :bot-id="botId"
                :has-avatar="hasAvatar"
                :display-name="displayName"
                :username="usernameLine"
                :cache-key="avatarCacheKey"
                :size="88"
              />
              <span v-else class="tg-avatar-ph">{{ avatarInitial }}</span>
            </div>
            <p class="tg-profile-name">{{ displayName || 'Имя бота' }}</p>
            <p class="tg-profile-kind">бот</p>
            <div class="tg-profile-actions">
              <div class="tg-action-pill">
                <span class="tg-action-icon" aria-hidden="true">💬</span>
                <span>Чат</span>
              </div>
              <div class="tg-action-pill">
                <span class="tg-action-icon" aria-hidden="true">🔔</span>
                <span>Звук</span>
              </div>
              <div class="tg-action-pill">
                <span class="tg-action-icon" aria-hidden="true">⋯</span>
                <span>Ещё</span>
              </div>
            </div>
          </div>

          <div class="tg-profile-section">
            <p class="tg-section-text">{{ aboutDisplay }}</p>
            <p class="tg-section-label">Информация</p>
          </div>

          <div class="tg-profile-section tg-profile-section--row">
            <div class="tg-username-row">
              <span class="tg-username-link">{{ usernameLine }}</span>
              <span class="tg-qr-placeholder" aria-hidden="true">▦</span>
            </div>
            <p class="tg-section-label">Имя пользователя</p>
          </div>

          <div v-if="publicLink" class="tg-profile-section tg-profile-section--links">
            <span class="tg-link-icon" aria-hidden="true">🔗</span>
            <span>1 ссылка</span>
          </div>
        </div>
      </div>

      <!-- 2. Чат до Start -->
      <div v-show="activeTab === 'prestart'" class="tg-screen tg-screen--chat">
        <header class="tg-chat-header tg-chat-header--light">
          <span class="tg-back" aria-hidden="true">‹</span>
          <div class="tg-chat-header-main">
            <div>
              <p class="tg-chat-name">{{ displayName || 'Бот' }}</p>
              <p class="tg-chat-sub">бот</p>
            </div>
          </div>
          <div class="tg-header-icons" aria-hidden="true">
            <span>⌕</span>
            <span>⋮</span>
          </div>
        </header>

        <div class="tg-chat-bg tg-chat-bg--doodle">
          <div class="tg-what-card">
            <p class="tg-what-title">Что может делать этот бот?</p>
            <p class="tg-what-text">{{ descriptionDisplay }}</p>
          </div>
        </div>

        <div class="tg-compose-bar">
          <span class="tg-compose-icon" aria-hidden="true">😊</span>
          <span class="tg-compose-input">Сообщение</span>
          <span class="tg-compose-icon" aria-hidden="true">📎</span>
        </div>
        <div class="tg-start-bar">
          <button type="button" class="tg-start-btn" disabled>НАЧАТЬ</button>
        </div>
      </div>

      <!-- 3. Чат после /start -->
      <div v-show="activeTab === 'afterstart'" class="tg-screen tg-screen--chat">
        <header class="tg-chat-header tg-chat-header--light">
          <span class="tg-back" aria-hidden="true">‹</span>
          <div class="tg-chat-header-main">
            <div>
              <p class="tg-chat-name">{{ displayName || 'Бот' }}</p>
              <p class="tg-chat-sub">бот</p>
            </div>
          </div>
          <div class="tg-header-icons" aria-hidden="true">
            <span>⌕</span>
            <span>⋮</span>
          </div>
        </header>

        <div class="tg-chat-bg tg-chat-bg--doodle tg-messages-area">
          <div class="tg-user-cmd">
            <span class="tg-cmd-bubble">/start</span>
          </div>

          <div class="tg-msg-incoming">
            <div class="tg-in-bubble">
              <p class="tg-bubble-text">{{ welcomeDisplay }}</p>
              <p v-if="publicLink && linkInWelcome" class="tg-bubble-link">{{ publicLink }}</p>

              <div v-if="showLinkPreview" class="tg-link-preview">
                <div class="tg-link-preview-body">
                  <p class="tg-lp-site">Telegram</p>
                  <p class="tg-lp-title">{{ displayName || 'Бот' }}</p>
                  <p class="tg-lp-desc">{{ linkPreviewDesc }}</p>
                </div>
                <BotAvatar
                  v-if="showServerAvatar"
                  :bot-id="botId"
                  :has-avatar="hasAvatar"
                  :display-name="displayName"
                  :username="usernameLine"
                  :cache-key="avatarCacheKey"
                  :size="48"
                  class="tg-lp-thumb"
                />
                <div v-else-if="resolvedPreviewUrl" class="tg-lp-thumb">
                  <img :src="resolvedPreviewUrl" alt="" />
                </div>
                <div v-else class="tg-lp-thumb tg-lp-thumb--ph">{{ avatarInitial }}</div>
              </div>

              <span class="tg-bubble-time">12:00</span>
            </div>
          </div>

          <button v-if="showButton" type="button" class="tg-inline-keyboard" disabled>
            <span>{{ buttonText }}</span>
            <span class="tg-inline-arrow" aria-hidden="true">↗</span>
          </button>
        </div>

        <div class="tg-compose-bar">
          <span class="tg-compose-icon" aria-hidden="true">😊</span>
          <span class="tg-compose-input">Сообщение</span>
          <span class="tg-compose-icon" aria-hidden="true">📎</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue';
import BotAvatar from './BotAvatar.vue';

const props = defineProps({
  displayName: { type: String, default: '' },
  username: { type: String, default: '' },
  aboutText: { type: String, default: '' },
  description: { type: String, default: '' },
  welcomeMessage: { type: String, default: '' },
  welcomeButtonEnabled: { type: Boolean, default: true },
  welcomeButtonText: { type: String, default: 'Перейти по ссылке' },
  avatarUrl: { type: String, default: null },
  avatarPreviewUrl: { type: String, default: null },
  botId: { type: Number, default: null },
  hasAvatar: { type: Boolean, default: false },
  avatarCacheKey: { type: String, default: '' },
  publicLink: { type: String, default: '' },
});

const resolvedPreviewUrl = computed(
  () => props.avatarPreviewUrl || props.avatarUrl || null
);

const showServerAvatar = computed(
  () => !resolvedPreviewUrl.value && props.botId && props.hasAvatar
);

const tabs = [
  { id: 'profile', label: 'Профиль' },
  { id: 'prestart', label: 'До Start' },
  { id: 'afterstart', label: 'Чат' },
];

const activeTab = ref('prestart');

const displayName = computed(() => props.displayName?.trim() || '');

const usernameLine = computed(() => {
  const u = (props.username || '').replace(/^@/, '').trim();
  return u ? `@${u}` : '@username_bot';
});

const avatarInitial = computed(() => {
  const n = displayName.value || 'B';
  return n.charAt(0).toUpperCase();
});

const aboutDisplay = computed(() => {
  const t = props.aboutText?.trim();
  if (t) return t;
  return 'Краткий текст в профиле бота (поле «О себе в профиле»).';
});

const descriptionDisplay = computed(() => {
  const t = props.description?.trim();
  if (t) return t;
  return 'Текст в блоке «Что может делать этот бот?» — поле «Описание в чате».';
});

const welcomeDisplay = computed(() => {
  const t = props.welcomeMessage?.trim();
  if (t) return t;
  return 'Приветствие после нажатия Start (поле «Приветствие»).';
});

const linkInWelcome = computed(() => {
  const link = props.publicLink?.trim();
  if (!link) return false;
  return welcomeDisplay.value.includes(link);
});

const showButton = computed(
  () => props.welcomeButtonEnabled !== false && (props.welcomeButtonText || props.publicLink)
);

const buttonText = computed(() => props.welcomeButtonText?.trim() || 'Перейти по ссылке');

const showLinkPreview = computed(() => !!props.publicLink?.trim() && !linkInWelcome.value);

const linkPreviewDesc = computed(() => {
  const d = props.description?.trim();
  if (d) return d.length > 80 ? `${d.slice(0, 80)}…` : d;
  const w = props.welcomeMessage?.trim();
  if (w) return w.length > 80 ? `${w.slice(0, 80)}…` : w;
  return 'Превью ссылки';
});
</script>

<style scoped>
.tg-preview {
  position: sticky;
  top: 1rem;
  align-self: start;
}

.tg-preview-head {
  margin-bottom: 0.5rem;
}

.tg-preview-title {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  font-weight: 600;
}

.tg-map {
  margin: 0.35rem 0 0;
  font-size: 0.68rem;
  line-height: 1.35;
}

.tg-tabs {
  display: flex;
  gap: 0.25rem;
  padding: 0.25rem;
  background: rgba(8, 12, 20, 0.5);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.tg-tab {
  flex: 1;
  padding: 0.4rem 0.45rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 0.68rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.tg-tab.active {
  background: var(--accent-soft);
  color: #93c5fd;
}

/* Phone frame */
.tg-phone {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: #fff;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
  min-height: 420px;
  display: flex;
  flex-direction: column;
}

.tg-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 400px;
  background: #fff;
}

/* ——— Profile modal ——— */
.tg-screen--profile {
  background: #f4f4f5;
}

.tg-modal {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 0.5rem;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.tg-modal-close {
  position: absolute;
  top: 0.5rem;
  right: 0.65rem;
  font-size: 1.25rem;
  color: #8e8e93;
  line-height: 1;
  z-index: 1;
}

.tg-profile-top {
  padding: 1.75rem 1rem 1rem;
  text-align: center;
  border-bottom: 1px solid #e8e8ed;
}

.tg-avatar-lg :deep(.bot-avatar-image) {
  margin: 0 auto;
  border: none;
}

.tg-lp-thumb :deep(.bot-avatar-image) {
  border: none;
}

.tg-avatar-lg {
  width: 96px;
  height: 96px;
  margin: 0 auto 0.65rem;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(135deg, #64b5f6, #42a5f5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.tg-avatar-lg img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.tg-avatar-ph {
  font-size: 2.25rem;
  font-weight: 600;
  color: #fff;
}

.tg-profile-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: #000;
  line-height: 1.25;
}

.tg-profile-kind {
  margin: 0.15rem 0 0.85rem;
  font-size: 0.8rem;
  color: #8e8e93;
}

.tg-profile-actions {
  display: flex;
  justify-content: center;
  gap: 0.5rem;
}

.tg-action-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  min-width: 4.5rem;
  padding: 0.45rem 0.35rem;
  background: #f2f2f7;
  border-radius: 8px;
  font-size: 0.65rem;
  color: #2481cc;
}

.tg-action-icon {
  font-size: 1rem;
  line-height: 1;
}

.tg-profile-section {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e8e8ed;
}

.tg-section-text {
  margin: 0;
  font-size: 0.82rem;
  color: #000;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-section-label {
  margin: 0.35rem 0 0;
  font-size: 0.72rem;
  color: #8e8e93;
}

.tg-username-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.tg-username-link {
  font-size: 0.88rem;
  color: #2481cc;
  font-weight: 500;
}

.tg-qr-placeholder {
  font-size: 1.1rem;
  color: #8e8e93;
}

.tg-profile-section--links {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #2481cc;
  border-bottom: none;
}

.tg-link-icon {
  font-size: 0.9rem;
}

/* ——— Chat screens ——— */
.tg-chat-header--light {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.55rem;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.tg-back {
  font-size: 1.5rem;
  color: #2481cc;
  line-height: 1;
  font-weight: 300;
}

.tg-chat-header-main {
  flex: 1;
  min-width: 0;
}

.tg-chat-name {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: #000;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tg-chat-sub {
  margin: 0;
  font-size: 0.72rem;
  color: #8e8e93;
}

.tg-header-icons {
  display: flex;
  gap: 0.65rem;
  font-size: 1rem;
  color: #8e8e93;
}

.tg-chat-bg {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
}

.tg-chat-bg--doodle {
  background-color: #9ecda8;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'%3E%3Cg fill='%237ab889' fill-opacity='0.25'%3E%3Ccircle cx='20' cy='25' r='4'/%3E%3Ccircle cx='80' cy='40' r='3'/%3E%3Ccircle cx='55' cy='90' r='5'/%3E%3Cpath d='M95 15h8v8h-8z'/%3E%3Cpath d='M10 70h6v6h-6z'/%3E%3C/g%3E%3C/svg%3E");
}

.tg-what-card {
  margin: auto 0.75rem;
  padding: 1rem 1.1rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  max-width: 92%;
  align-self: center;
}

.tg-what-title {
  margin: 0 0 0.65rem;
  font-size: 0.88rem;
  font-weight: 700;
  color: #000;
}

.tg-what-text {
  margin: 0;
  font-size: 0.8rem;
  color: #000;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-start-bar {
  padding: 0.5rem 0.75rem 0.65rem;
  background: #fff;
  border-top: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.tg-start-btn {
  width: 100%;
  padding: 0.5rem;
  border: none;
  border-radius: 8px;
  background: #2481cc;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: default;
}

.tg-compose-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.55rem;
  background: #fff;
  border-top: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.tg-compose-input {
  flex: 1;
  font-size: 0.78rem;
  color: #8e8e93;
}

.tg-compose-icon {
  font-size: 1rem;
  opacity: 0.7;
}

/* Messages */
.tg-messages-area {
  padding: 0.5rem 0.55rem 0.35rem;
  gap: 0.35rem;
}

.tg-user-cmd {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.25rem;
}

.tg-cmd-bubble {
  padding: 0.35rem 0.55rem;
  background: #eeffde;
  border-radius: 10px 10px 4px 10px;
  font-size: 0.8rem;
  color: #000;
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.08);
}

.tg-msg-incoming {
  display: flex;
  justify-content: flex-start;
  max-width: 95%;
}

.tg-in-bubble {
  position: relative;
  padding: 0.45rem 0.55rem 0.3rem;
  background: #fff;
  border-radius: 4px 12px 12px 12px;
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.1);
  max-width: 100%;
}

.tg-bubble-text {
  margin: 0;
  font-size: 0.8rem;
  color: #000;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-bubble-link {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: #2481cc;
  word-break: break-all;
}

.tg-link-preview {
  display: flex;
  gap: 0.45rem;
  margin-top: 0.45rem;
  padding: 0.4rem 0.45rem 0.4rem 0.5rem;
  border-left: 3px solid #4fae4e;
  background: #f5f9f4;
  border-radius: 0 6px 6px 0;
  overflow: hidden;
}

.tg-link-preview-body {
  flex: 1;
  min-width: 0;
}

.tg-lp-site {
  margin: 0;
  font-size: 0.68rem;
  color: #4fae4e;
  font-weight: 500;
}

.tg-lp-title {
  margin: 0.1rem 0 0;
  font-size: 0.78rem;
  font-weight: 700;
  color: #000;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tg-lp-desc {
  margin: 0.15rem 0 0;
  font-size: 0.68rem;
  color: #8e8e93;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tg-lp-thumb {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #e0e0e0;
}

.tg-lp-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.tg-lp-thumb--ph {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
  background: #4fae4e;
}

.tg-bubble-time {
  display: block;
  margin-top: 0.2rem;
  font-size: 0.62rem;
  color: #8e8e93;
  text-align: right;
}

.tg-inline-keyboard {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  width: 100%;
  max-width: 95%;
  margin-top: 0.15rem;
  padding: 0.45rem 0.65rem;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.75);
  font-size: 0.8rem;
  font-weight: 500;
  color: #2481cc;
  cursor: default;
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.06);
}

.tg-inline-arrow {
  font-size: 0.75rem;
  opacity: 0.8;
}

@media (max-width: 960px) {
  .tg-preview {
    position: static;
    margin-top: 1rem;
  }
}
</style>
