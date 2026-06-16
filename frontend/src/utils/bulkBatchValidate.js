/**
 * Проверки партии ботов перед генерацией и созданием.
 * @returns {{ errors: string[], warnings: string[] }}
 */
import { accountDisplayLabel } from './accountLabel';

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
    if (acc.is_banned) {
      errors.push(`Строка ${n}: аккаунт «${accountDisplayLabel(acc)}» забанен.`);
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
        `Аккаунт «${accountDisplayLabel(acc)}»: в партии ${lineNums.length} ботов, свободно слотов: ${Math.max(0, slots)}.`
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
import { resolveRowAvatar } from './bulkBotAvatars';

export function validateManualBulkBatch(rows, account, sharedTexts, options = {}) {
  const {
    linkSource = 'batch',
    campaignResourceUrl = '',
    batchUrl = '',
    multiAccount = false,
    readyAccounts = [],
  } = options;
  const errors = [];
  const warnings = [];

  let slots = 0;

  if (multiAccount) {
    if (!readyAccounts.length) {
      errors.push('Нет готовых аккаунтов для мультиаккаунтного режима.');
      return { errors, warnings };
    }
    slots = readyAccounts.reduce(
      (sum, a) => sum + Math.max(0, a.max_bots_limit - a.bots_created),
      0
    );
    if (slots <= 0) {
      errors.push('На всех аккаунтах достигнут лимит ботов.');
    }
  } else if (!account) {
    errors.push('Выберите аккаунт Telegram.');
    return { errors, warnings };
  } else {
    if (account.is_banned) {
      errors.push('Выбранный аккаунт забанен и не может использоваться для создания ботов.');
    }

    if (account.bots_created >= account.max_bots_limit) {
      errors.push(`На аккаунте достигнут лимит ботов (${account.max_bots_limit}).`);
    }

    slots = Math.max(0, account.max_bots_limit - account.bots_created);
  }

  const readyRows = rows.filter((r) => r.displayName?.trim() && r.username?.trim());

  if (!readyRows.length) {
    errors.push('Добавьте хотя бы одного бота с именем и username.');
  } else if (readyRows.length > slots) {
    const slotLabel = multiAccount
      ? `суммарно свободно слотов: ${slots}`
      : `свободно слотов на аккаунте: ${slots}`;
    errors.push(`В партии ${readyRows.length} ботов, ${slotLabel}.`);
  }

  if (!sharedTexts?.description?.trim()) {
    errors.push('Заполните описание (плакат до Start).');
  }
  if (!sharedTexts?.welcome_message?.trim()) {
    errors.push('Заполните сообщение после Start.');
  }

  if (linkSource === 'campaign' && !campaignResourceUrl?.trim()) {
    errors.push('В кампании не задана ссылка на сервис.');
  }
  if (linkSource === 'batch' && !batchUrl?.trim()) {
    errors.push('Укажите общую ссылку для партии.');
  }
  if (linkSource === 'per_bot') {
    const withoutUrl = readyRows.filter((r) => !r.targetUrl?.trim());
    if (withoutUrl.length) {
      errors.push('Укажите ссылку для каждого бота в колонке «Ссылка».');
    }
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

  const withoutAvatar = readyRows.filter((r) => !resolveRowAvatar(r, rows));
  if (withoutAvatar.length) {
    warnings.push(
      `${withoutAvatar.length} бот(ов) без аватара — в Telegram останется пустая картинка.`
    );
  }

  return { errors, warnings };
}

/** Ссылка строки (только для режима per_bot). */
export function rowTargetUrl(row) {
  return row.targetUrl?.trim() || '';
}
