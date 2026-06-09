/**
 * Проверки партии ботов перед генерацией и созданием.
 * @returns {{ errors: string[], warnings: string[] }}
 */
export function validateBulkBatch(rows, readyAccounts) {
  const errors = [];
  const warnings = [];
  const usage = new Map();

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const n = i + 1;
    if (!row.accountId) continue;

    const prev = usage.get(row.accountId) || [];
    prev.push(n);
    usage.set(row.accountId, prev);

    const acc = readyAccounts.find((a) => a.id === row.accountId);
    if (!acc) {
      errors.push(`Строка ${n}: аккаунт недоступен для создания ботов.`);
      continue;
    }
    if (acc.bots_created >= acc.max_bots_limit) {
      errors.push(`Строка ${n}: на аккаунте достигнут лимит ботов (${acc.max_bots_limit}).`);
    }
  }

  for (const [, lineNums] of usage) {
    if (lineNums.length > 1) {
      warnings.push(
        `Аккаунт повторяется в строках ${lineNums.join(', ')} — убедитесь, что это намеренно.`
      );
    }
  }

  for (const [accountId, lineNums] of usage) {
    const acc = readyAccounts.find((a) => a.id === accountId);
    if (!acc) continue;
    const slots = acc.max_bots_limit - acc.bots_created;
    if (lineNums.length > slots) {
      errors.push(
        `Аккаунт «${acc.label || acc.phone || accountId}»: в партии ${lineNums.length} ботов, свободно слотов: ${Math.max(0, slots)}.`
      );
    }
  }

  const forAi = rows.filter((r) => r.accountId && r.keyword?.trim());
  if (!forAi.length) {
    warnings.push('Для AI-генерации укажите фразу хотя бы в одной строке с выбранным аккаунтом.');
  }

  return { errors, warnings };
}

/**
 * Проверки ручной массовой партии (один аккаунт, общие тексты).
 * @returns {{ errors: string[], warnings: string[] }}
 */
export function validateManualBulkBatch(rows, account, sharedTexts, defaultUrl = '') {
  const errors = [];
  const warnings = [];

  if (!account) {
    errors.push('Выберите аккаунт Telegram.');
    return { errors, warnings };
  }

  if (account.bots_created >= account.max_bots_limit) {
    errors.push(`На аккаунте достигнут лимит ботов (${account.max_bots_limit}).`);
  }

  const slots = Math.max(0, account.max_bots_limit - account.bots_created);
  const readyRows = rows.filter((r) => r.displayName?.trim() && r.username?.trim());

  if (!readyRows.length) {
    errors.push('Добавьте хотя бы одного бота с именем и username.');
  } else if (readyRows.length > slots) {
    errors.push(
      `В партии ${readyRows.length} ботов, свободно слотов на аккаунте: ${slots}.`
    );
  }

  if (!sharedTexts?.description?.trim()) {
    errors.push('Заполните описание (плакат до Start).');
  }
  if (!sharedTexts?.welcome_message?.trim()) {
    errors.push('Заполните сообщение после Start.');
  }

  const usernames = new Map();
  for (let i = 0; i < rows.length; i++) {
    const u = rows[i].username?.replace(/^@/, '').trim().toLowerCase();
    if (!u) continue;
    if (usernames.has(u)) {
      errors.push(`Username @${u} повторяется в строках ${usernames.get(u)} и ${i + 1}.`);
    } else {
      usernames.set(u, i + 1);
    }
  }

  const withoutAvatar = readyRows.filter((r) => !r.avatarFile);
  if (withoutAvatar.length) {
    warnings.push(
      `${withoutAvatar.length} бот(ов) без аватара — в Telegram останется пустая картинка.`
    );
  }

  const withoutUrl = readyRows.filter((r) => !rowTargetUrl(r, defaultUrl)?.trim());
  if (withoutUrl.length) {
    errors.push('Укажите ссылку на сервис (общую или для каждого бота).');
  }

  return { errors, warnings };
}

/** Ссылка строки: своя или общая по умолчанию. */
export function rowTargetUrl(row, defaultUrl = '') {
  const custom = row.targetUrl?.trim();
  if (custom) return custom;
  return defaultUrl?.trim() || '';
}
