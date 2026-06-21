import { formatApiError } from '../utils/apiErrorMessage';
import { defineStore } from 'pinia';
import { settingsService } from '../services/settingsService';

const DEFAULT_PACING = {
  inter_bot_delay_sec: 45,
  op_delay_sec: 4,
  conv_delay_sec: 2,
  batch_size: 5,
  batch_cooldown_sec: 180,
  post_throttle_delay_sec: 30,
  max_server_flood_wait: 180,
};

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    botfatherPacing: { ...DEFAULT_PACING },
    loaded: false,
    loading: false,
    error: null,
  }),

  actions: {
    async fetchBotfatherPacing({ force = false } = {}) {
      if (this.loaded && !force) return this.botfatherPacing;
      this.loading = true;
      this.error = null;
      try {
        const pacing = await settingsService.getBotfatherPacing();
        if (pacing) {
          this.botfatherPacing = { ...DEFAULT_PACING, ...pacing };
        }
        this.loaded = true;
        return this.botfatherPacing;
      } catch (e) {
        this.error = formatApiError(e, 'Не удалось загрузить настройки');
        return this.botfatherPacing;
      } finally {
        this.loading = false;
      }
    },

    async saveBotfatherPacing(pacing) {
      const saved = await settingsService.updateBotfatherPacing(pacing);
      this.botfatherPacing = { ...DEFAULT_PACING, ...saved };
      this.loaded = true;
      return this.botfatherPacing;
    },
  },
});
