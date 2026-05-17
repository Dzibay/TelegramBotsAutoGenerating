import apiClient from '../utils/apiClient';

export const prepService = {
  async listJobs() {
    const res = await apiClient.get('/account-prep/jobs');
    return res.data?.jobs ?? [];
  },

  async getJob(jobId) {
    const res = await apiClient.get(`/account-prep/jobs/${jobId}`);
    return { job: res.data?.job, accounts: res.data?.accounts ?? [] };
  },

  async getLogs(jobId, afterId = 0) {
    const res = await apiClient.get(`/account-prep/jobs/${jobId}/logs`, {
      params: { after_id: afterId },
    });
    return res.data?.logs ?? [];
  },

  async createJob({ files, options, newPassword, currentPassword, passwordHint, autoStart }) {
    const form = new FormData();
    for (const file of files) {
      form.append('files', file);
    }
    form.append('options_json', JSON.stringify(options));
    if (newPassword) form.append('new_password', newPassword);
    if (currentPassword) form.append('current_password', currentPassword);
    if (passwordHint) form.append('password_hint', passwordHint);
    form.append('auto_start', autoStart ? 'true' : 'false');

    const res = await apiClient.post('/account-prep/jobs', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return res.data?.job;
  },

  async startJob(jobId, { newPassword, currentPassword, passwordHint }) {
    const form = new FormData();
    if (newPassword) form.append('new_password', newPassword);
    if (currentPassword) form.append('current_password', currentPassword);
    if (passwordHint) form.append('password_hint', passwordHint || '');
    const res = await apiClient.post(`/account-prep/jobs/${jobId}/start`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data?.job;
  },
};
