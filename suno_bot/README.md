# Suno Music Bot — Telegram-бот для генерации музыки

Telegram-бот для генерации музыки через [SunoAPI.org](https://sunoapi.org/).

## Требования

- Python 3.10+
- API-ключ SunoAPI (получить на [sunoapi.org/api-key](https://sunoapi.org/api-key))
- Токен Telegram-бота ([@BotFather](https://t.me/BotFather))

## Установка

```bash
cd suno_bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Конфигурация

Создайте файл `.env` или экспортируйте переменные:

```bash
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export SUNO_API_KEY="your_suno_api_key"
```

## Запуск

```bash
python bot.py
```

Или с загрузкой `.env`:

```bash
# если используете python-dotenv
pip install python-dotenv
# и добавьте в config.py загрузку dotenv
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и инструкция |
| `/balance` | Показать остаток кредитов SunoAPI |
| `/instrumental` | Переключить режим без вокала |
| Текст | Описание песни → генерация |

## Примеры запросов

- «грустная песня про расставание в стиле инди-рок»
- «весёлый джаз про утро в Париже»
- «эпичный саундтрек для фэнтези-игры»

## Деплой

### Локально / VPS

```bash
# systemd service (пример)
sudo nano /etc/systemd/system/suno-bot.service
```

```ini
[Unit]
Description=Suno Music Telegram Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/suno_bot
Environment="TELEGRAM_BOT_TOKEN=..."
Environment="SUNO_API_KEY=..."
ExecStart=/path/to/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable suno-bot
sudo systemctl start suno-bot
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t suno-bot .
docker run -d --env-file .env suno-bot
```

## Обработка ошибок

- При ошибке API бот сообщает пользователю и логирует исключение
- Таймаут генерации — 5 минут
- При падении API бот не завершает работу, обрабатывает исключения

## Структура проекта

```
suno_bot/
├── bot.py          # хендлеры Telegram
├── suno_api.py     # обёртка SunoAPI
├── config.py       # конфиг из env
├── requirements.txt
└── README.md
```
