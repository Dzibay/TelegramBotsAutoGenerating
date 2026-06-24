<template>
  <div class="import-bots">
    <header class="page-header">
      <RouterLink :to="{ name: 'campaign-workspace', params: { id: campaignId } }" class="back">
        ← Назад в кампанию
      </RouterLink>
      <h1>Импорт ботов по токену</h1>
      <p class="subtitle">
        Добавьте в систему уже созданных вручную ботов. Данные (username, имя, описание,
        about) считываются из Telegram автоматически — сам бот не меняется.
        Аккаунт и аватар остаются пустыми, тексты приветствия берутся из настроек кампании,
        ссылка — из реферального API кампании по username.
      </p>
    </header>

    <section class="card block">
      <div class="form-group">
        <label for="tokens">Токены ботов</label>
        <textarea
          id="tokens"
          v-model="tokensRaw"
          rows="8"
          placeholder="Один токен на строку, например:&#10;123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11&#10;234567:..."
          :disabled="loading"
        />
        <p class="field-hint">
          Распознано токенов: <strong>{{ parsedTokens.length }}</strong>
          <span v-if="parsedTokens.length > 100" class="error-text"> — максимум 100 за раз</span>
        </p>
      </div>

      <p v-if="submitError" class="error-text">{{ submitError }}</p>

      <div class="actions">
        <button
          type="button"
          class="btn"
          :disabled="loading || parsedTokens.length === 0 || parsedTokens.length > 100"
          @click="runImport"
        >
          {{ loading ? 'Импорт…' : `Импортировать (${parsedTokens.length})` }}
        </button>
      </div>
    </section>

    <section v-if="result" class="card block result">
      <h3 class="block-title">Результат импорта</h3>
      <p class="summary">
        Импортировано: <strong class="ok">{{ result.imported_count }}</strong>,
        ошибок: <strong :class="{ 'error-text': result.failed_count > 0 }">{{ result.failed_count }}</strong>
      </p>

      <ul v-if="result.bots?.length" class="imported-list">
        <li v-for="bot in result.bots" :key="bot.id">
          ✅ @{{ bot.username }} — {{ bot.display_name }}
        </li>
      </ul>

      <ul v-if="result.errors?.length" class="error-list">
        <li v-for="(err, i) in result.errors" :key="i">
          ⚠️ Токен …{{ err.token_tail }}: {{ err.error }}
        </li>
      </ul>

      <RouterLink :to="{ name: 'campaign-workspace', params: { id: campaignId } }" class="btn-ghost btn-sm">
        Перейти к ботам кампании
      </RouterLink>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { botService } from '../services/botService';
import { formatApiError } from '../utils/apiErrorMessage.js';

const route = useRoute();
const campaignId = computed(() => Number(route.params.id));

const tokensRaw = ref('');
const loading = ref(false);
const submitError = ref('');
const result = ref(null);

const parsedTokens = computed(() => {
  const seen = new Set();
  const out = [];
  for (const part of tokensRaw.value.split(/[\s,;]+/)) {
    const tok = part.trim();
    if (tok && !seen.has(tok)) {
      seen.add(tok);
      out.push(tok);
    }
  }
  return out;
});

async function runImport() {
  if (loading.value || parsedTokens.value.length === 0) return;
  loading.value = true;
  submitError.value = '';
  result.value = null;
  try {
    result.value = await botService.importByTokens(campaignId.value, parsedTokens.value);
  } catch (e) {
    submitError.value = formatApiError(e, 'Не удалось импортировать ботов');
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.import-bots {
  max-width: 720px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 1.5rem;
}

.back {
  display: inline-block;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}

.subtitle {
  color: var(--text-muted, #888);
  font-size: 0.9rem;
  line-height: 1.5;
}

.block {
  margin-bottom: 1.25rem;
}

.block-title {
  margin-top: 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

textarea {
  width: 100%;
  font-family: monospace;
  resize: vertical;
}

.field-hint {
  font-size: 0.8rem;
  color: var(--text-muted, #888);
}

.actions {
  margin-top: 1rem;
}

.summary {
  font-size: 0.95rem;
}

.ok {
  color: var(--success, #2e9e5b);
}

.imported-list,
.error-list {
  list-style: none;
  padding: 0;
  margin: 0.75rem 0;
  font-size: 0.85rem;
  line-height: 1.6;
}

.error-list {
  color: var(--danger, #d04444);
}
</style>
