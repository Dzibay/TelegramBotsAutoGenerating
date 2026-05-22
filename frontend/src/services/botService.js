import apiClient from '../utils/apiClient';

export const botService = {
  async listGrouped() {
    const res = await apiClient.get('/bots', { params: { grouped: true } });
    return res.data?.campaigns ?? [];
  },

  async list(campaignId) {
    const params = campaignId ? { campaign_id: campaignId } : {};
    const res = await apiClient.get('/bots', { params });
    return res.data?.bots ?? [];
  },

  async get(id) {
    const res = await apiClient.get(`/bots/${id}`);
    return res.data?.bot;
  },

  avatarUrl(bot) {
    if (!bot?.avatar_url) return null;
    const base = import.meta.env.DEV
      ? (import.meta.env.VITE_API_BASE_URL || '/api/v1')
      : '/api/v1';
    return `${base.replace(/\/$/, '')}${bot.avatar_url}`;
  },

  async generateDraft({ campaignId, accountId, targetUrl, keyword, redirectSlug, linkMode = 'redirect' }) {
    const res = await apiClient.post('/bots/generate-draft', {
      campaign_id: campaignId,
      telegram_account_id: accountId,
      target_url: targetUrl,
      keyword: keyword || null,
      redirect_slug: redirectSlug || null,
      link_mode: linkMode,
    });
    return res.data?.draft;
  },

  async create(payload, avatarFile = null) {
    const form = new FormData();
    form.append('data', JSON.stringify(payload));
    if (avatarFile) form.append('avatar', avatarFile);
    const res = await apiClient.post('/bots', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });
    return res.data?.bot;
  },

  async update(id, payload) {
    const res = await apiClient.patch(`/bots/${id}`, payload);
    return res.data?.bot;
  },

  async uploadAvatar(id, file) {
    const form = new FormData();
    form.append('avatar', file);
    const res = await apiClient.post(`/bots/${id}/avatar`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return res.data?.bot;
  },

  async remove(id) {
    await apiClient.delete(`/bots/${id}`);
  },

  async start(id) {
    const res = await apiClient.post(`/bots/${id}/start`);
    return res.data?.bot;
  },

  async stop(id) {
    const res = await apiClient.post(`/bots/${id}/stop`);
    return res.data?.bot;
  },

  async verify(id) {
    const res = await apiClient.post(`/bots/${id}/verify`);
    return res.data;
  },

  async batchCreate(bots) {
    const res = await apiClient.post('/bots/batch-create', { bots }, { timeout: 600000 });
    return res.data;
  },
};
