<template>
  <div class="link-mode-field">
    <label class="field-label">Ссылка в текстах бота</label>
    <div class="radio-group">
      <label class="radio-option">
        <input type="radio" :checked="modelValue === 'redirect'" @change="emit('update:modelValue', 'redirect')" />
        <span>
          <strong>Считать переходы</strong> (рекомендуется)
          <small>Короткая ссылка в боте, статистика кликов в панели</small>
        </span>
      </label>
      <label class="radio-option">
        <input type="radio" :checked="modelValue === 'direct'" @change="emit('update:modelValue', 'direct')" />
        <span>
          <strong>Прямая ссылка на сайт</strong>
          <small>В боте сразу откроется адрес из поля «Ссылка на сервис»</small>
        </span>
      </label>
    </div>
    <p v-if="previewUrl" class="preview">
      В боте пользователи увидят:
      <code>{{ previewUrl }}</code>
    </p>
  </div>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: 'redirect' },
  previewUrl: { type: String, default: '' },
});

const emit = defineEmits(['update:modelValue']);
</script>

<style scoped>
.link-mode-field {
  margin: 1rem 0;
}

.field-label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.radio-option {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.875rem;
}

.radio-option:has(input:checked) {
  border-color: var(--accent);
  background: rgba(59, 130, 246, 0.06);
}

.radio-option input {
  width: auto;
  margin-top: 0.15rem;
}

.radio-option small {
  display: block;
  color: var(--muted);
  font-size: 0.75rem;
  margin-top: 0.15rem;
}

.preview {
  margin: 0.6rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.preview code {
  display: block;
  margin-top: 0.25rem;
  word-break: break-all;
  font-size: 0.75rem;
}
</style>
