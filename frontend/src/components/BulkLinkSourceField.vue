<template>
  <div class="link-source-block">
    <span class="block-label">Ссылки для ботов</span>
    <div class="radio-group">
      <label v-if="usesReferralApi" class="radio-opt">
        <input
          type="radio"
          name="bulk-link-source"
          :checked="linkSource === 'referral'"
          @change="emit('update:linkSource', 'referral')"
        />
        <span>
          <strong>Автоматически через API</strong>
          <small>Уникальная ссылка для каждого бота после создания в BotFather</small>
        </span>
      </label>

      <label v-if="showPerBotOption" class="radio-opt">
        <input
          type="radio"
          name="bulk-link-source"
          :checked="linkSource === 'per_bot'"
          @change="emit('update:linkSource', 'per_bot')"
        />
        <span>
          <strong>Своя ссылка для каждого бота</strong>
          <small>Указывается отдельно в таблице ботов</small>
        </span>
      </label>

      <label class="radio-opt" :class="{ 'radio-opt--disabled': !campaignResourceUrl }">
        <input
          type="radio"
          name="bulk-link-source"
          :checked="linkSource === 'campaign'"
          :disabled="!campaignResourceUrl"
          @change="emit('update:linkSource', 'campaign')"
        />
        <span>
          <strong>Ссылка из кампании</strong>
          <small v-if="campaignResourceUrl">{{ campaignResourceUrl }}</small>
          <small v-else>Не задана в настройках кампании</small>
        </span>
      </label>

      <label class="radio-opt">
        <input
          type="radio"
          name="bulk-link-source"
          :checked="linkSource === 'batch'"
          @change="emit('update:linkSource', 'batch')"
        />
        <span>
          <strong>Общая ссылка для всей партии</strong>
          <small>Один адрес для всех ботов в этой партии</small>
        </span>
      </label>
    </div>

    <div v-if="linkSource === 'batch'" class="form-group nested">
      <label>URL для всех ботов *</label>
      <input
        :value="batchUrl"
        type="url"
        placeholder="https://example.com"
        @input="emit('update:batchUrl', $event.target.value)"
      />
    </div>

    <div v-if="showRedirectToggle" class="redirect-block">
      <label class="check">
        <input
          type="checkbox"
          :checked="trackClicks"
          @change="emit('update:trackClicks', $event.target.checked)"
        />
        Считать переходы через сервис
      </label>
      <p class="field-hint">
        В текстах бота будет короткая ссылка <code>/go/…</code> — клики учитываются в панели.
        Без галочки пользователи сразу увидят прямой адрес сайта.
      </p>
      <p v-if="linkPreview" class="link-preview">
        В боте пользователи увидят:
        <code>{{ linkPreview }}</code>
      </p>
      <p v-else-if="trackClicks" class="link-preview muted">
        Для каждого бота будет своя короткая ссылка на выбранный адрес.
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  linkSource: { type: String, required: true },
  batchUrl: { type: String, default: '' },
  trackClicks: { type: Boolean, default: true },
  usesReferralApi: { type: Boolean, default: false },
  campaignResourceUrl: { type: String, default: '' },
  showPerBotOption: { type: Boolean, default: true },
  linkPreview: { type: String, default: '' },
});

const emit = defineEmits(['update:linkSource', 'update:batchUrl', 'update:trackClicks']);

const showRedirectToggle = computed(() =>
  ['campaign', 'batch', 'per_bot'].includes(props.linkSource)
);
</script>

<style scoped>
.link-source-block {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border-radius: 8px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.block-label {
  display: block;
  font-weight: 600;
  font-size: 0.9rem;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.radio-opt {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding: 0.7rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  line-height: 1.35;
  cursor: pointer;
  background: rgba(8, 12, 20, 0.35);
  transition: border-color 0.15s, background 0.15s;
}

.radio-opt:hover:not(.radio-opt--disabled) {
  border-color: var(--border-strong);
}

.radio-opt:has(input:checked) {
  border-color: rgba(59, 130, 246, 0.5);
  background: var(--accent-soft);
}

.radio-opt--disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.radio-opt input {
  width: auto;
  flex-shrink: 0;
  margin-top: 0.2rem;
  padding: 0;
}

.radio-opt strong {
  display: block;
  font-weight: 600;
}

.radio-opt small {
  display: block;
  margin-top: 0.2rem;
  color: var(--muted);
  font-size: 0.75rem;
  word-break: break-all;
}

.nested {
  margin: 0;
}

.redirect-block {
  padding-top: 0.25rem;
}

.link-preview {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.link-preview code {
  display: block;
  margin-top: 0.25rem;
  word-break: break-all;
  font-size: 0.75rem;
}
</style>
