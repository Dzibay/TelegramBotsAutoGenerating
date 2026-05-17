export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: '/auth/login',
    ME: '/auth/me',
  },
  CAMPAIGNS: {
    LIST: '/campaigns',
    CREATE: '/campaigns',
    CREATE_FULL: '/campaigns/create-full',
    GET: (id) => `/campaigns/${id}`,
    BOTS: (id) => `/campaigns/${id}/bots`,
    ACCOUNTS: (id) => `/campaigns/${id}/accounts`,
    VERIFY_ACCOUNTS: (id) => `/campaigns/${id}/accounts/verify-all`,
    VERIFY_ACCOUNT: (campaignId, accountId) =>
      `/campaigns/${campaignId}/accounts/${accountId}/verify`,
    REMOVE_ACCOUNT: (campaignId, accountId) =>
      `/campaigns/${campaignId}/accounts/${accountId}`,
    UPLOAD_ACCOUNT: (id) => `/campaigns/${id}/accounts`,
    UPLOAD_BATCH: (id) => `/campaigns/${id}/accounts/batch`,
    START: (id) => `/campaigns/${id}/start`,
  },
  JOBS: {
    GET: (id) => `/jobs/${id}`,
    LOGS: (id) => `/jobs/${id}/logs`,
  },
  ACCOUNT_PREP: {
    JOBS: '/account-prep/jobs',
    JOB: (id) => `/account-prep/jobs/${id}`,
    LOGS: (id) => `/account-prep/jobs/${id}/logs`,
  },
  BOTS: {
    LIST: '/bots',
    GET: (id) => `/bots/${id}`,
    GENERATE: '/bots/generate-draft',
    START: (id) => `/bots/${id}/start`,
    STOP: (id) => `/bots/${id}/stop`,
  },
  PREPARED_ACCOUNTS: {
    LIST: '/prepared-accounts',
    GET: (id) => `/prepared-accounts/${id}`,
    ATTACH: (campaignId) => `/campaigns/${campaignId}/accounts/from-prepared`,
  },
  HEALTH: '/health',
};
