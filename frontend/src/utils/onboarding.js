const STORAGE_KEY = 'tg_bots_onboarding_done';

export function shouldShowOnboarding() {
  return !localStorage.getItem(STORAGE_KEY);
}

export function dismissOnboarding() {
  localStorage.setItem(STORAGE_KEY, '1');
}
