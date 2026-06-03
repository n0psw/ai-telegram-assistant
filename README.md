# AI Telegram Assistant — Центр Красок #1

Telegram-бот с AI-ассистентом, который отвечает на вопросы о компании «Центр Красок #1» на основе собранной информации с сайта https://centr-krasok.kz/

## Возможности

- Работает как обычный чат — без команд и меню
- Отвечает на вопросы о компании, продукции, брендах, контактах, доставке
- Сохраняет контекст диалога (последние 10 пар сообщений)
- Защита от «галлюцинаций» — бот отвечает только на основе собранной базы знаний
- Корректно обрабатывает нерелевантные вопросы

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Создайте бота через [@BotFather](https://t.me/BotFather) и получите токен
2. Получите API-ключ OpenAI на https://platform.openai.com/
3. Заполните файл `.env`:

```
TELEGRAM_BOT_TOKEN=ваш_токен_бота
OPENAI_API_KEY=ваш_ключ_openai
OPENAI_MODEL=gpt-4o-mini
```

## Запуск

```bash
python bot.py
```

## Структура проекта

```
bot/
├── bot.py                 # Основной файл бота
├── company_knowledge.py   # Структурированная база знаний о компании
├── requirements.txt       # Зависимости
├── .env                   # Конфигурация (токены)
└── README.md
```

## Источники информации

- https://centr-krasok.kz/ — главная страница
- https://centr-krasok.kz/about/ — о магазине
- https://centr-krasok.kz/about/contacts/ — контакты
- https://centr-krasok.kz/brands/ — бренды
- Социальные сети: Instagram, Facebook, YouTube
