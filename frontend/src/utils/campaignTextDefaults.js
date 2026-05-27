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
}

export function campaignTextDefaultsSnapshot(campaign) {
  return {
    description: campaign?.default_description || '',
    about_text: campaign?.default_about_text || '',
    welcome_message: campaign?.default_welcome_message || '',
  };
}
