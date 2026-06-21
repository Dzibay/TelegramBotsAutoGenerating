/** Тексты долгих операций для индикатора прогресса (понятные пользователю). */
export const TASK_PRESETS = {
  VERIFY_ACCOUNT: {
    title: 'Проверка аккаунта',
    icon: 'telegram',
    estimatedSec: 25,
    steps: [
      'Подключение к Telegram…',
      'Проверка входа в аккаунт…',
      'Получение списка ботов…',
      'Обновление данных…',
    ],
    verboseSteps: [
      'API: POST verify account',
      'Telethon: load tdata session',
      'Telegram: getMe()',
      'BotFather: /mybots — подсчёт ботов',
      'DB: status=ready, sync bots_created',
    ],
  },
  VERIFY_ALL_ACCOUNTS: {
    title: 'Проверка аккаунтов',
    icon: 'telegram',
    estimatedSec: 90,
    steps: [
      'Проверяем аккаунты по очереди…',
      'Подключение к Telegram…',
      'Синхронизация списка ботов…',
      'Это может занять несколько минут…',
    ],
    verboseSteps: [
      'API: POST verify-all',
      'Для каждого аккаунта: tdata → Telegram → BotFather /mybots',
      'Обновление статусов и счётчиков в БД',
    ],
  },
  LIST_ACCOUNT_BOTS: {
    title: 'Список ботов',
    icon: 'botfather',
    estimatedSec: 35,
    steps: [
      'Подключение к Telegram…',
      'Получаем список ботов в Telegram…',
      'Загрузка данных…',
      'Если ботов много — читаем дальше…',
    ],
    verboseSteps: [
      'API: GET account bots',
      'BotFather: /mybots (+ пагинация)',
      'Сверка с bots в кампании',
    ],
  },
  DELETE_ACCOUNT_BOT: {
    title: 'Удаление бота',
    icon: 'botfather',
    estimatedSec: 40,
    steps: [
      'Подключение к Telegram…',
      'Удаляем бота в Telegram…',
      'Подтверждение…',
      'Обновление списка…',
    ],
    verboseSteps: [
      'API: DELETE account bot',
      'BotFather: /deletebot → подтверждение',
      'DB: удаление записи (если in_app)',
      'Повторный запрос списка ботов',
    ],
  },
  ATTACH_ACCOUNTS: {
    title: 'Добавление аккаунтов',
    icon: 'telegram',
    estimatedSec: 60,
    steps: [
      'Добавляем в кампанию…',
      'Проверка входа в Telegram…',
      'Синхронизация ботов…',
    ],
    verboseSteps: [
      'API: attach prepared accounts',
      'Копирование tdata на сервер',
      'Авто verify-all для новых аккаунтов',
    ],
  },
  CREATE_BOT: {
    title: 'Создание бота',
    icon: 'botfather',
    estimatedSec: 120,
    steps: [
      'Подключение к аккаунту…',
      'Регистрация бота в Telegram…',
      'Имя и username…',
      'Настройка описания и аватара…',
      'Сохранение…',
    ],
    verboseSteps: [
      'Telethon: сессия аккаунта',
      'BotFather: /newbot → имя → username → token',
      'BotFather: /setuserpic, /setdescription, /setabouttext',
      'DB: INSERT bot, encrypt token',
      'Bot runner: status active (если auto_start)',
    ],
  },
  BULK_CREATE_BOTS: {
    title: 'Массовое создание ботов',
    icon: 'botfather',
    estimatedSec: 180,
    steps: [
      'Подключение к аккаунту…',
      'Регистрация бота в Telegram…',
      'Имя, username и аватар…',
      'Описание и приветствие…',
      'Следующий бот в очереди…',
    ],
    verboseSteps: [
      'API: POST create bot (sequential)',
      'Полный цикл BotFather на каждого бота',
      'Паузы между ботами (rate limit)',
    ],
  },
  DELETE_BOT: {
    title: 'Удаление бота',
    icon: 'botfather',
    estimatedSec: 45,
    steps: [
      'Подключение к аккаунту…',
      'Удаление в Telegram…',
      'Обновление в приложении…',
    ],
    verboseSteps: ['API: DELETE bot', 'DB: CASCADE / soft delete'],
  },
  SYNC_BOTFATHER: {
    title: 'Сохранение бота',
    icon: 'botfather',
    estimatedSec: 15,
    steps: [
      'Сохранение в базе…',
      'Подготовка фоновой синхронизации…',
    ],
    verboseSteps: [
      'API: PATCH /bots/{id} — быстрое сохранение',
      'BotFather: /setname, /setdescription, /setabouttext — в фоне на сервере',
    ],
  },
  START_CAMPAIGN: {
    title: 'Массовое создание ботов',
    icon: 'botfather',
    estimatedSec: 30,
    steps: [
      'Запуск задачи…',
      'Подключение к аккаунтам…',
      'Создание ботов — смотрите журнал…',
    ],
    verboseSteps: [
      'API: POST /campaigns/{id}/start',
      'Redis: enqueue creation_job',
      'Worker: CreationPipeline',
    ],
  },
  CREATE_CAMPAIGN_FULL: {
    title: 'Создание кампании',
    icon: 'botfather',
    estimatedSec: 120,
    steps: [
      'Создаём кампанию…',
      'Добавляем аккаунты…',
      'Проверка и синхронизация…',
      'Запуск создания ботов (если включено)…',
    ],
    verboseSteps: [
      'API: create-full (multipart)',
      'Attach prepared + verify-all',
      'Optional: start creation job',
    ],
  },
  PREP_ACCOUNTS: {
    title: 'Подготовка аккаунтов',
    icon: 'botfather',
    estimatedSec: 45,
    steps: [
      'Загрузка файлов…',
      'Постановка в очередь…',
      'Настройка безопасности и ботов…',
    ],
    verboseSteps: [
      'API: POST account-prep/jobs',
      'Worker: tdata extract, security steps',
      'BotFather: delete_all_bots (если включено)',
      'Pool: prepared_accounts',
    ],
  },
};
