import { defineStore } from 'pinia';
import { authService } from '../services/authService';
import { formatApiError } from '../utils/apiErrorMessage';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    loading: false,
    error: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.user,
  },

  actions: {
    async fetchUser() {
      if (!authService.getToken()) {
        this.user = null;
        return null;
      }
      this.loading = true;
      this.error = null;
      try {
        this.user = await authService.me();
        return this.user;
      } catch {
        this.user = null;
        authService.logout();
        return null;
      } finally {
        this.loading = false;
      }
    },

    async login(password) {
      this.loading = true;
      this.error = null;
      try {
        const data = await authService.login(password);
        this.user = data.user;
        return data;
      } catch (e) {
        this.error = formatApiError(e, 'Неверный пароль');
        throw e;
      } finally {
        this.loading = false;
      }
    },

    logout() {
      authService.logout();
      this.user = null;
    },
  },
});
