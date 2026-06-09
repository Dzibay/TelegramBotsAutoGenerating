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
  },
  SYNC_BOTFATHER: {
    title: 'Обновление профиля бота',
    icon: 'botfather',
    estimatedSec: 90,
    steps: [
      'Подключение к аккаунту…',
      'Обновление имени…',
      'Описание и текст «О боте»…',
      'Загрузка аватара…',
    ],
  },
  START_CAMPAIGN: {
    title: 'Массовое создание ботов',
    icon: 'botfather',
    estimatedSec: 30,
    steps: [
      'Запуск задачи…',
      'Подключение к аккаунтам…',
      'Создание ботов — смотрите журнал слева…',
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
  },
};
