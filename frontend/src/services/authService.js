import apiClient from '../utils/apiClient';
import { API_ENDPOINTS } from '../config/api';

export const authService = {
  async login(password) {
    const res = await apiClient.post(API_ENDPOINTS.AUTH.LOGIN, { password });
    if (res.data?.access_token) {
      localStorage.setItem('access_token', res.data.access_token);
    }
    return res.data;
  },

  async me() {
    const res = await apiClient.get(API_ENDPOINTS.AUTH.ME);
    return res.data?.user;
  },

  logout() {
    localStorage.removeItem('access_token');
  },

  getToken() {
    return localStorage.getItem('access_token');
  },
};
