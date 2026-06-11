<template>
  <div class="bot-avatar-image" :style="boxStyle" :class="{ 'bot-avatar-image--loaded': !!src }">
    <img v-if="src" :src="src" alt="" />
    <span v-else class="bot-avatar-image-fallback">{{ initial }}</span>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue';
import { botService } from '../services/botService';

const props = defineProps({
  bot: { type: Object, default: null },
  botId: { type: Number, default: null },
  hasAvatar: { type: Boolean, default: null },
  displayName: { type: String, default: '' },
  username: { type: String, default: '' },
  size: { type: Number, default: 40 },
  cacheKey: { type: String, default: '' },
});

const src = ref(null);
let objectUrl = null;

const resolvedId = computed(() => props.bot?.id ?? props.botId ?? null);
const resolvedHasAvatar = computed(() => {
  if (props.hasAvatar != null) return props.hasAvatar;
  return !!props.bot?.has_avatar;
});

const initial = computed(() => {
  const name =
    props.displayName ||
    props.username ||
    props.bot?.display_name ||
    props.bot?.username ||
    '?';
  return String(name).replace(/^@/, '').charAt(0).toUpperCase() || '?';
});

const boxStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.max(12, Math.round(props.size * 0.38))}px`,
}));

function revoke() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
  src.value = null;
}

async function load() {
  revoke();
  const id = resolvedId.value;
  if (!id || !resolvedHasAvatar.value) return;
  try {
    const key = props.cacheKey || props.bot?.updated_at || '';
    objectUrl = await botService.loadAvatarObjectUrl(id, key);
    src.value = objectUrl;
  } catch {
    src.value = null;
  }
}

watch(
  () => [resolvedId.value, resolvedHasAvatar.value, props.cacheKey, props.bot?.updated_at],
  load,
  { immediate: true }
);

onUnmounted(revoke);

defineExpose({ reload: load });
</script>

<style scoped>
.bot-avatar-image {
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.12);
  color: #93c5fd;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.bot-avatar-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.bot-avatar-image-fallback {
  font-weight: 600;
  line-height: 1;
  user-select: none;
}
</style>
