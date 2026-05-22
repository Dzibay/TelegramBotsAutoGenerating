<template>
  <div class="keywords-editor">
    <div class="form-group">
      <label>Тематика ботов</label>
      <textarea
        v-model="nicheLocal"
        rows="3"
        placeholder="Например: боты для поиска VPN, прокси, обход блокировок…"
        @input="emitNiche"
      />
      <p class="field-hint">
        Помогает автоматически подобрать ключевые слова и тексты. На каждое слово обычно создаётся отдельный бот.
      </p>
    </div>

    <div class="form-group">
      <div class="label-row">
        <label>Ключевые слова кампании</label>
        <span class="count">{{ keywordLines.length }} шт.</span>
      </div>
      <textarea
        v-model="keywordsText"
        rows="8"
        placeholder="Одно ключевое слово или фраза на строку&#10;vpn бот&#10;бесплатный прокси telegram&#10;обход блокировок бот"
        @input="onKeywordsInput"
      />
      <p class="field-hint">
        Поисковые фразы, по которым пользователи находят бота. При массовом создании — один бот на одно слово.
      </p>
    </div>

    <div class="gen-row">
      <label class="gen-count">
        Сгенерировать
        <input v-model.number="genCount" type="number" min="3" max="50" />
        слов
      </label>
      <label class="checkbox-row">
        <input v-model="genMerge" type="checkbox" />
        Добавить к существующим
      </label>
      <button
        type="button"
        class="btn btn-ai"
        :disabled="generating"
        @click="onGenerate"
      >
        {{ generating ? 'Генерация…' : '✨ Сгенерировать ключевые слова' }}
      </button>
    </div>

    <p v-if="genError" class="error-text">{{ genError }}</p>
    <p v-if="genHint" class="field-hint success-hint">{{ genHint }}</p>

    <div v-if="keywordLines.length" class="chips">
      <span v-for="(kw, i) in keywordLines" :key="i" class="chip">{{ kw }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { campaignService } from '../services/campaignService';

const props = defineProps({
  campaignId: { type: Number, default: null },
  keywords: { type: Array, default: () => [] },
  nicheDescription: { type: String, default: '' },
});

const emit = defineEmits(['update:keywords', 'update:nicheDescription', 'generated']);

const nicheLocal = ref(props.nicheDescription || '');
const keywordsText = ref('');
const genCount = ref(10);
const genMerge = ref(true);
const generating = ref(false);
const genError = ref(null);
const genHint = ref(null);

const keywordLines = computed(() =>
  keywordsText.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
);

function syncFromProps() {
  keywordsText.value = (props.keywords || []).join('\n');
  nicheLocal.value = props.nicheDescription || '';
}

watch(() => props.keywords, syncFromProps, { immediate: true });
watch(() => props.nicheDescription, (v) => {
  nicheLocal.value = v || '';
});

function onKeywordsInput() {
  emit('update:keywords', keywordLines.value);
}

function emitNiche() {
  emit('update:nicheDescription', nicheLocal.value.trim());
}

async function onGenerate() {
  if (!props.campaignId) {
    genError.value = 'Сначала сохраните кампанию';
    return;
  }
  generating.value = true;
  genError.value = null;
  genHint.value = null;
  try {
    await campaignService.update(props.campaignId, {
      niche_description: nicheLocal.value.trim() || null,
      keywords: keywordLines.value,
    });
    const { keywords } = await campaignService.generateKeywords(props.campaignId, {
      count: genCount.value,
      merge: genMerge.value,
    });
    keywordsText.value = (keywords || []).join('\n');
    emit('update:keywords', keywords || []);
    emit('generated', keywords);
    genHint.value = `Добавлено ключевых слов: ${(keywords || []).length}`;
  } catch (e) {
    genError.value = e.response?.data?.error || 'Не удалось сгенерировать';
  } finally {
    generating.value = false;
  }
}

defineExpose({ keywordLines, nicheLocal });
</script>

<style scoped>
.keywords-editor {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.count {
  font-size: 0.8rem;
  color: var(--muted);
}

.gen-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.gen-count {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.875rem;
}

.gen-count input {
  width: 4rem;
}

.btn-ai {
  margin-left: auto;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.chip {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--muted);
}

.success-hint {
  color: #4ade80;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.checkbox-row input {
  width: auto;
}
</style>
