import axios from 'axios';
import { formatApiError } from './apiErrorMessage';

function getApiBaseUrl() {
  if (import.meta.env.DEV) {
    return import.meta.env.VITE_API_BASE_URL || '/api/v1';
  }
  return '/api/v1';
}

const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    error.apiMessage = formatApiError(error);
    if (error.response?.status === 401) {
      const isAuth = error.config?.url?.includes('/auth/');
      if (!isAuth) {
        localStorage.removeItem('access_token');
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
