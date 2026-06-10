import { defineStore } from 'pinia';

const STORAGE_KEY = 'tg_bots_ui_prefs';

function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function savePrefs(prefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
}

export const useUiPrefsStore = defineStore('uiPrefs', {
  state: () => {
    const saved = loadPrefs();
    return {
      verboseLogs: !!saved.verboseLogs,
    };
  },

  actions: {
    setVerboseLogs(value) {
      this.verboseLogs = !!value;
      savePrefs({ verboseLogs: this.verboseLogs });
    },

    toggleVerboseLogs() {
      this.setVerboseLogs(!this.verboseLogs);
    },
  },
});
