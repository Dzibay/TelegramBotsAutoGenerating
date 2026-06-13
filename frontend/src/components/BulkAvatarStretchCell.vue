<template>
  <div
    class="stretch-cell"
    :class="{ 'stretch-cell--active': isDragging, 'stretch-cell--has-image': previewUrl }"
    :style="{ minHeight: `${span * rowHeight}px` }"
  >
    <button
      type="button"
      class="avatar-surface"
      :title="previewUrl ? 'Сменить общую аватарку' : 'Загрузить аватарку для нескольких ботов'"
      @click="fileInput?.click()"
    >
      <img v-if="previewUrl" :src="previewUrl" alt="" class="avatar-img" />
      <div v-else class="avatar-empty">
        <span class="avatar-plus">+</span>
        <span v-if="span > 1" class="avatar-span-badge">{{ span }}</span>
      </div>
      <div v-if="previewUrl && span > 1" class="span-overlay">
        <span>{{ span }} бот(ов)</span>
      </div>
    </button>

    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      class="file-input"
      @change="onFileChange"
    />

    <button
      v-if="previewUrl"
      type="button"
      class="clear-btn"
      title="Убрать аватарку"
      @click="clear"
    >
      ×
    </button>

    <div
      class="stretch-handle"
      :title="`Потяните — аватарка на ${span} бот(ов). Макс. ${maxSpan}`"
      @pointerdown="onStretchStart"
    >
      <span class="grip-line" />
      <span class="grip-line" />
      <span class="grip-icon">⇕</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const ROW_HEIGHT = 52;

const props = defineProps({
  previewUrl: { type: String, default: null },
  span: { type: Number, default: 1 },
  maxSpan: { type: Number, default: 1 },
  rowHeight: { type: Number, default: ROW_HEIGHT },
});

const emit = defineEmits(['update:file', 'update:preview', 'update:span']);

const fileInput = ref(null);
const isDragging = ref(false);

function onFileChange(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) {
    alert('Файл больше 5 МБ');
    e.target.value = '';
    return;
  }
  emit('update:file', file);
  emit('update:preview', URL.createObjectURL(file));
}

function clear() {
  if (fileInput.value) fileInput.value.value = '';
  emit('update:file', null);
  emit('update:preview', null);
}

function onStretchStart(e) {
  if (e.button !== 0) return;
  e.preventDefault();
  isDragging.value = true;
  const startY = e.clientY;
  const startSpan = props.span;

  const onMove = (ev) => {
    const deltaRows = Math.round((ev.clientY - startY) / props.rowHeight);
    const next = Math.max(1, Math.min(props.maxSpan, startSpan + deltaRows));
    if (next !== props.span) emit('update:span', next);
  };

  const onUp = () => {
    isDragging.value = false;
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
  };

  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
}

defineExpose({ clear });
</script>

<style scoped>
.stretch-cell {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 3.25rem;
  transition: min-height 0.15s ease;
}

.stretch-cell--active {
  z-index: 2;
}

.stretch-cell--active .stretch-handle {
  background: rgba(59, 130, 246, 0.25);
  border-color: rgba(96, 165, 250, 0.7);
}

.avatar-surface {
  flex: 1;
  min-height: 2.5rem;
  margin: 0;
  padding: 0;
  border: 1px dashed rgba(139, 156, 179, 0.45);
  border-radius: 10px;
  background: linear-gradient(165deg, rgba(15, 23, 42, 0.65), rgba(30, 41, 59, 0.35));
  cursor: pointer;
  overflow: hidden;
  position: relative;
  display: block;
  width: 100%;
}

.avatar-surface:hover {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.2);
}

.stretch-cell--has-image .avatar-surface {
  border-style: solid;
  border-color: rgba(59, 130, 246, 0.35);
}

.avatar-img {
  width: 100%;
  height: 100%;
  min-height: 2.5rem;
  object-fit: cover;
  display: block;
}

.avatar-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
  min-height: 2.5rem;
  padding: 0.35rem;
}

.avatar-plus {
  font-size: 1.15rem;
  line-height: 1;
  color: var(--muted);
}

.avatar-span-badge {
  font-size: 0.62rem;
  font-weight: 600;
  color: #93c5fd;
  background: rgba(59, 130, 246, 0.15);
  padding: 0.1rem 0.35rem;
  border-radius: 999px;
}

.span-overlay {
  position: absolute;
  inset: auto 0 0 0;
  padding: 0.2rem 0.35rem;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.72));
  font-size: 0.62rem;
  font-weight: 600;
  color: #e2e8f0;
  text-align: center;
}

.file-input {
  display: none;
}

.clear-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: #ef4444;
  color: #fff;
  font-size: 0.7rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  z-index: 3;
}

.stretch-handle {
  flex-shrink: 0;
  margin-top: 0.2rem;
  height: 1.1rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: rgba(8, 12, 20, 0.85);
  cursor: ns-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.2rem;
  touch-action: none;
  user-select: none;
}

.stretch-handle:hover {
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(59, 130, 246, 0.12);
}

.grip-line {
  width: 10px;
  height: 2px;
  border-radius: 1px;
  background: rgba(148, 163, 184, 0.7);
}

.grip-icon {
  font-size: 0.55rem;
  color: #93c5fd;
  line-height: 1;
}
</style>
