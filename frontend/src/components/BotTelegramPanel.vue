<template>
  <section class="card bot-telegram-panel">
    <h2 class="panel-title">Ссылки и статистика</h2>

    <div v-if="promoLink" class="promo-block">
      <p class="block-label">Трекинг-ссылка (в боте и описании)</p>
      <div class="link-row">
        <a :href="promoLink" target="_blank" rel="noopener noreferrer" class="tg-link">
          {{ promoLink }}
        </a>
        <button type="button" class="btn btn-sm btn-ghost" @click="copyPromo">
          {{ copiedPromo ? 'Скопировано' : 'Копировать' }}
        </button>
      </div>
      <p class="stats">
        Кликов по ссылке: <strong>{{ bot.click_count ?? 0 }}</strong>
      </p>
      <p v-if="bot.target_url" class="target-hint">
        Редирект на: <span class="muted">{{ bot.target_url }}</span>
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
      <p class="hint">Отправьте <code>/start</code> — должно прийти сообщение о переезде с трекинг-ссылкой.</p>
    </div>

    <p v-if="!promoLink && !tgLink" class="muted">Ссылки появятся после создания бота.</p>

    <button
      type="button"
      class="btn btn-ghost verify-btn"
      :disabled="verifying || !botId"
      @click="onVerify"
    >
      {{ verifying ? 'Проверка…' : 'Проверить токен (Telegram API)' }}
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
const promoLink = computed(() => props.bot?.tracking_url);
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
  try {
    const result = await botService.verify(botId.value);
    verifyResult.value = result;
    emit('verified', result);
  } catch (e) {
    verifyError.value = e.response?.data?.error || 'Ошибка проверки';
    verifyResult.value = null;
  } finally {
    verifying.value = false;
  }
}

watch(
  () => [props.bot?.id, props.autoVerify],
  () => {
    verifyResult.value = null;
    verifyError.value = null;
    if (props.autoVerify && props.bot?.has_token && props.bot?.id) {
      onVerify();
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.bot-telegram-panel {
  margin-bottom: 1.25rem;
  padding: 1rem 1.15rem;
}

.panel-title {
  margin: 0 0 0.75rem;
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
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.tg-link {
  flex: 1;
  min-width: 12rem;
  font-size: 0.85rem;
  word-break: break-all;
  color: var(--accent);
}

.stats {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
}

.target-hint {
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  word-break: break-all;
}

.hint {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.hint code {
  font-size: 0.85em;
  padding: 0.1rem 0.35rem;
  background: var(--bg);
  border-radius: 4px;
}

.verify-btn {
  width: 100%;
  margin-top: 0.5rem;
}

.verify-result {
  margin-top: 0.5rem;
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  font-size: 0.875rem;
}

.verify-result.ok {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
}

.verify-result.warn {
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.35);
}

.verify-msg {
  margin: 0;
}

.verify-hint {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.8rem;
}
</style>
