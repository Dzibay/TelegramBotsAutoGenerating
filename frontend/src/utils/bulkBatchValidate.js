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
