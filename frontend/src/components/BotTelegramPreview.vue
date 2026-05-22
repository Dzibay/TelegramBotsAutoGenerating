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
    </div>

    <div class="tg-phone">
      <!-- Профиль бота (страница Info) -->
      <div v-show="activeTab === 'profile'" class="tg-screen tg-screen--profile">
        <div class="tg-profile-hero">
          <div class="tg-avatar-lg">
            <img v-if="avatarUrl" :src="avatarUrl" alt="" />
            <span v-else class="tg-avatar-ph">{{ avatarInitial }}</span>
          </div>
          <p class="tg-name">{{ displayName || 'Имя бота' }}</p>
          <p class="tg-username">{{ usernameLine }}</p>
        </div>
        <div class="tg-profile-block">
          <p class="tg-block-label">О себе</p>
          <p class="tg-block-text">{{ aboutDisplay }}</p>
        </div>
        <p class="tg-profile-hint muted">Экран профиля — «О себе» (до 120 символов).</p>
      </div>

      <!-- Пустой чат до Start: описание + кнопка -->
      <div v-show="activeTab === 'prestart'" class="tg-screen tg-screen--chat">
        <header class="tg-chat-header">
          <span class="tg-back">‹</span>
          <div class="tg-chat-header-main">
            <div class="tg-avatar-sm">
              <img v-if="avatarUrl" :src="avatarUrl" alt="" />
              <span v-else>{{ avatarInitial }}</span>
            </div>
            <div>
              <p class="tg-chat-name">{{ displayName || 'Бот' }}</p>
              <p class="tg-chat-sub">бот</p>
            </div>
          </div>
        </header>
        <div class="tg-prestart-body">
          <div class="tg-prestart-card">
            <div class="tg-avatar-md">
              <img v-if="avatarUrl" :src="avatarUrl" alt="" />
              <span v-else>{{ avatarInitial }}</span>
            </div>
            <p class="tg-prestart-name">{{ displayName || 'Имя бота' }}</p>
            <p class="tg-prestart-desc">{{ descriptionDisplay }}</p>
          </div>
        </div>
        <div class="tg-start-bar">
          <button type="button" class="tg-start-btn" disabled>НАЧАТЬ</button>
        </div>
        <p class="tg-screen-hint muted">Плакат в пустом чате — «Описание в чате» (до Start).</p>
      </div>

      <!-- После Start: приветствие -->
      <div v-show="activeTab === 'afterstart'" class="tg-screen tg-screen--chat">
        <header class="tg-chat-header">
          <span class="tg-back">‹</span>
          <div class="tg-chat-header-main">
            <div class="tg-avatar-sm">
              <img v-if="avatarUrl" :src="avatarUrl" alt="" />
              <span v-else>{{ avatarInitial }}</span>
            </div>
            <div>
              <p class="tg-chat-name">{{ displayName || 'Бот' }}</p>
              <p class="tg-chat-sub">бот</p>
            </div>
          </div>
        </header>
        <div class="tg-messages">
          <p class="tg-date">сегодня</p>
          <div class="tg-bubble-wrap">
            <div class="tg-avatar-xs">
              <img v-if="avatarUrl" :src="avatarUrl" alt="" />
              <span v-else>{{ avatarInitial }}</span>
            </div>
            <div class="tg-bubble">
              <p class="tg-bubble-text">{{ welcomeDisplay }}</p>
              <span class="tg-bubble-time">12:00</span>
            </div>
          </div>
          <a
            v-if="showButton"
            :href="publicLink || '#'"
            class="tg-inline-btn"
            target="_blank"
            rel="noopener noreferrer"
            @click.prevent
          >
            {{ buttonText }}
          </a>
        </div>
        <p class="tg-screen-hint muted">Первое сообщение после нажатия «Начать».</p>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  displayName: { type: String, default: '' },
  username: { type: String, default: '' },
  aboutText: { type: String, default: '' },
  description: { type: String, default: '' },
  welcomeMessage: { type: String, default: '' },
  welcomeButtonEnabled: { type: Boolean, default: true },
  welcomeButtonText: { type: String, default: 'Перейти по ссылке' },
  avatarUrl: { type: String, default: null },
  publicLink: { type: String, default: '' },
});

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
  return 'Здесь будет короткий текст «О себе» в профиле бота.';
});

const descriptionDisplay = computed(() => {
  const t = props.description?.trim();
  if (t) return t;
  return 'Здесь будет описание в пустом чате — пользователь увидит его до кнопки «Начать».';
});

const welcomeDisplay = computed(() => {
  const t = props.welcomeMessage?.trim();
  if (t) return t;
  return 'Здесь будет приветствие после нажатия Start.';
});

const showButton = computed(
  () => props.welcomeButtonEnabled !== false && (props.welcomeButtonText || props.publicLink)
);

const buttonText = computed(() => props.welcomeButtonText?.trim() || 'Перейти по ссылке');
</script>

<style scoped>
.tg-preview {
  position: sticky;
  top: 1rem;
  align-self: start;
}

.tg-preview-head {
  margin-bottom: 0.65rem;
}

.tg-preview-title {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  font-weight: 600;
}

.tg-tabs {
  display: flex;
  gap: 0.25rem;
  padding: 0.2rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.tg-tab {
  flex: 1;
  padding: 0.35rem 0.4rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 0.68rem;
  font-weight: 500;
  cursor: pointer;
}

.tg-tab.active {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.tg-phone {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid #2a3544;
  background: #0e1621;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
  min-height: 380px;
  display: flex;
  flex-direction: column;
}

.tg-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 360px;
}

.tg-screen-hint {
  margin: 0;
  padding: 0.4rem 0.65rem 0.5rem;
  font-size: 0.65rem;
  text-align: center;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* Profile */
.tg-profile-hero {
  padding: 1.5rem 1rem 1rem;
  text-align: center;
  background: linear-gradient(180deg, #17212b 0%, #0e1621 100%);
}

.tg-avatar-lg {
  width: 88px;
  height: 88px;
  margin: 0 auto 0.75rem;
  border-radius: 50%;
  overflow: hidden;
  background: #2481cc;
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
  font-size: 2rem;
  font-weight: 600;
  color: #fff;
}

.tg-name {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #fff;
}

.tg-username {
  margin: 0.2rem 0 0;
  font-size: 0.8rem;
  color: #6ab2f2;
}

.tg-profile-block {
  margin: 0.75rem 1rem;
  padding: 0.65rem 0.75rem;
  background: #17212b;
  border-radius: 10px;
}

.tg-block-label {
  margin: 0 0 0.25rem;
  font-size: 0.7rem;
  color: #6d7f8f;
}

.tg-block-text {
  margin: 0;
  font-size: 0.82rem;
  color: #e4ecf2;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-profile-hint {
  margin: auto 0 0;
  padding: 0.5rem;
  font-size: 0.65rem;
  text-align: center;
}

/* Chat header */
.tg-chat-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.65rem;
  background: #17212b;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.tg-back {
  font-size: 1.4rem;
  color: #6ab2f2;
  line-height: 1;
}

.tg-chat-header-main {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.tg-avatar-sm {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  background: #2481cc;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
}

.tg-avatar-sm img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.tg-chat-name {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tg-chat-sub {
  margin: 0;
  font-size: 0.72rem;
  color: #6d7f8f;
}

/* Pre-start */
.tg-prestart-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: #0e1621;
}

.tg-prestart-card {
  text-align: center;
  max-width: 240px;
}

.tg-avatar-md {
  width: 72px;
  height: 72px;
  margin: 0 auto 0.65rem;
  border-radius: 50%;
  overflow: hidden;
  background: #2481cc;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 600;
  color: #fff;
}

.tg-avatar-md img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.tg-prestart-name {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #fff;
}

.tg-prestart-desc {
  margin: 0;
  font-size: 0.8rem;
  color: #8b9cb3;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-start-bar {
  padding: 0.65rem 1rem 0.85rem;
  background: #17212b;
}

.tg-start-btn {
  width: 100%;
  padding: 0.55rem;
  border: none;
  border-radius: 8px;
  background: #2481cc;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: default;
  opacity: 0.95;
}

/* Messages */
.tg-messages {
  flex: 1;
  padding: 0.65rem 0.75rem 1rem;
  background: #0e1621;
  overflow-y: auto;
}

.tg-date {
  margin: 0 0 0.5rem;
  text-align: center;
  font-size: 0.68rem;
  color: #6d7f8f;
}

.tg-bubble-wrap {
  display: flex;
  align-items: flex-end;
  gap: 0.35rem;
  max-width: 92%;
}

.tg-avatar-xs {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  overflow: hidden;
  background: #2481cc;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  font-weight: 600;
  color: #fff;
}

.tg-avatar-xs img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.tg-bubble {
  position: relative;
  padding: 0.45rem 0.55rem 0.35rem;
  background: #182533;
  border-radius: 12px 12px 12px 4px;
  max-width: 100%;
}

.tg-bubble-text {
  margin: 0;
  font-size: 0.82rem;
  color: #e4ecf2;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.tg-bubble-time {
  display: block;
  margin-top: 0.15rem;
  font-size: 0.62rem;
  color: #6d7f8f;
  text-align: right;
}

.tg-inline-btn {
  display: block;
  margin: 0.35rem 0 0 2rem;
  padding: 0.45rem 0.75rem;
  max-width: calc(100% - 2rem);
  text-align: center;
  font-size: 0.8rem;
  font-weight: 500;
  color: #6ab2f2;
  background: rgba(36, 129, 204, 0.15);
  border: 1px solid rgba(106, 178, 242, 0.35);
  border-radius: 8px;
  text-decoration: none;
  cursor: default;
}

.tg-inline-btn:hover {
  text-decoration: none;
}

@media (max-width: 960px) {
  .tg-preview {
    position: static;
    margin-top: 1rem;
  }
}
</style>
