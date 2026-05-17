-- Расширение kind для аудита AI (ключевые слова кампании)
ALTER TABLE ai_generations DROP CONSTRAINT IF EXISTS ai_generations_kind_check;
ALTER TABLE ai_generations ADD CONSTRAINT ai_generations_kind_check
    CHECK (kind IN (
        'niche_analysis',
        'bot_profile',
        'welcome_message',
        'avatar_prompt',
        'campaign_keywords'
    ));
