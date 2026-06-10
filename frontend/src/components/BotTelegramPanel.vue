<template>
  <section class="card bot-telegram-panel">
    <h2 class="panel-title">Ссылки и статистика</h2>

    <div v-if="promoLink" class="promo-block">
      <p class="block-label">
        {{ isRedirect ? 'Ссылка в боте (со счётчиком)' : 'Прямая ссылка в боте' }}
      </p>
      <div class="link-row">
        <a :href="promoLink" target="_blank" rel="noopener noreferrer" class="tg-link">
          {{ promoLink }}
        </a>
        <button type="button" class="btn btn-sm btn-ghost" @click="copyPromo">
          {{ copiedPromo ? 'Скопировано' : 'Копировать' }}
        </button>
      </div>
      <p v-if="isRedirect" class="stats">
        Кликов по ссылке: <strong>{{ bot.click_count ?? 0 }}</strong>
      </p>
      <p v-if="isRedirect && bot.target_url" class="target-hint">
        Редирект на: <span class="muted">{{ bot.target_url }}</span>
      </p>
      <p v-else-if="!isRedirect" class="target-hint muted">
        Счётчик переходов не ведётся — пользователи идут напрямую на сайт.
      </p>
    </div>

    <div v-if="tgLink" class="tg-block">
      <p class="block-label">Чат с ботом в Telegram</p>
      <div class="link-row">
        <a :href="tgLink" target="_blank" rel="noopener noreferrer" class="tg-link">{{ tgLink }}</a>
        <a :href="tgLink" target="_blank" rel="noopener noreferrer" class="btn btn-sm">
          Открыть ↗
        </a>
      </div>
      <p class="hint">Отправьте <code>/start</code> — должно прийти сообщение с выбранной ссылкой.</p>
    </div>

    <p v-if="!promoLink && !tgLink" class="muted">Ссылки появятся после создания бота.</p>

    <button
      type="button"
      class="btn btn-ghost verify-btn"
      :disabled="verifying || !botId"
      @click="onVerify"
    >
      {{ verifying ? 'Проверка…' : 'Проверить, что бот отвечает' }}
    </button>

    <p v-if="verifyError" class="error-text">{{ verifyError }}</p>
    <div
      v-else-if="verifyResult"
      class="verify-result"
      :class="verifyResult.verified ? 'ok' : 'warn'"
    >
      <p class="verify-msg">{{ verifyResult.message }}</p>
      <p v-if="verifyResult.polling_hint" class="verify-hint">{{ verifyResult.polling_hint }}</p>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { botService } from '../services/botService';
import { telegramBotUrl } from '../utils/botLink';

const props = defineProps({
  bot: { type: Object, required: true },
  autoVerify: { type: Boolean, default: false },
});

const emit = defineEmits(['verified']);

const copiedPromo = ref(false);
const verifying = ref(false);
const verifyError = ref(null);
const verifyResult = ref(null);

const botId = computed(() => props.bot?.id);
const isRedirect = computed(() => (props.bot?.link_mode || 'redirect') === 'redirect');
const promoLink = computed(
  () => props.bot?.public_link || (isRedirect.value ? props.bot?.tracking_url : props.bot?.target_url)
);
const tgLink = computed(
  () => props.bot?.telegram_url || telegramBotUrl(props.bot?.username),
);

async function copyPromo() {
  if (!promoLink.value) return;
  try {
    await navigator.clipboard.writeText(promoLink.value);
    copiedPromo.value = true;
    setTimeout(() => {
      copiedPromo.value = false;
    }, 2000);
  } catch {
    verifyError.value = 'Не удалось скопировать';
  }
}

async function onVerify() {
  if (!botId.value) return;
  verifying.value = true;
  verifyError.value = null;
  verifyResult.value = null;
  try {
    const data = await botService.verify(botId.value);
    verifyResult.value = data;
    emit('verified', data);
  } catch (e) {
    verifyError.value = e.response?.data?.error || 'Ошибка проверки';
  } finally {
    verifying.value = false;
  }
}

watch(
  () => props.autoVerify,
  (v) => {
    if (v && botId.value) onVerify();
  },
  { immediate: true }
);
</script>

<style scoped>
.bot-telegram-panel {
  margin-bottom: 1.25rem;
}

.panel-title {
  margin: 0 0 1rem;
  font-size: 1rem;
}

.promo-block,
.tg-block {
  margin-bottom: 1rem;
}

.block-label {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  color: var(--muted);
}

.link-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.tg-link {
  word-break: break-all;
  font-size: 0.875rem;
  color: var(--accent);
}

.stats {
  margin: 0.5rem 0 0;
  font-size: 0.875rem;
}

.target-hint {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
}

.hint {
  margin: 0.5rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.verify-btn {
  margin-top: 0.5rem;
}

.verify-result {
  margin-top: 0.75rem;
  padding: 0.75rem 0.9rem;
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
}

.verify-result.ok {
  background: var(--success-soft);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

.verify-result.warn {
  background: var(--warning-soft);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fbbf24;
}

.verify-msg {
  margin: 0;
}

.verify-hint {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}
</style>
