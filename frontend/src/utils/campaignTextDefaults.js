/** Подставляет дефолтные тексты кампании в пустые поля черновика бота. */
export function applyCampaignTextDefaults(target, campaign) {
  if (!target || !campaign) return;
  if (!target.description?.trim() && campaign.default_description) {
    target.description = campaign.default_description;
  }
  if (!target.about_text?.trim() && campaign.default_about_text) {
    target.about_text = campaign.default_about_text;
  }
  if (!target.welcome_message?.trim() && campaign.default_welcome_message) {
    target.welcome_message = campaign.default_welcome_message;
  }
  if (!target.welcome_button_text?.trim() && campaign.default_welcome_button_text?.trim()) {
    target.welcome_button_text = campaign.default_welcome_button_text.trim();
  }
  if (
    typeof campaign.default_welcome_button_enabled === 'boolean' &&
    target.welcome_button_enabled === undefined
  ) {
    target.welcome_button_enabled = campaign.default_welcome_button_enabled;
  }
}

export function campaignTextDefaultsSnapshot(campaign) {
  return {
    description: campaign?.default_description || '',
    about_text: campaign?.default_about_text || '',
    welcome_message: campaign?.default_welcome_message || '',
    welcome_button_enabled: campaign?.default_welcome_button_enabled !== false,
    welcome_button_text: campaign?.default_welcome_button_text?.trim() || 'Перейти по ссылке',
  };
}

/** Подставляет дефолты кнопки из кампании в форму создания ботов. */
export function applyCampaignButtonDefaults(target, campaign) {
  if (!target || !campaign) return;
  if (typeof campaign.default_welcome_button_enabled === 'boolean') {
    target.welcome_button_enabled = campaign.default_welcome_button_enabled;
  }
  if (campaign.default_welcome_button_text?.trim()) {
    target.welcome_button_text = campaign.default_welcome_button_text.trim();
  }
}
