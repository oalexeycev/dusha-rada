"""Конфигурация бота из переменных окружения."""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    """Настройки приложения."""

    telegram_bot_token: str
    suno_api_key: str
    suno_base_url: str = "https://api.sunoapi.org"
    poll_interval_sec: int = 10
    generation_timeout_sec: int = 300  # 5 минут

    @classmethod
    def from_env(cls) -> "Config":
        """Загрузить конфиг из переменных окружения."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        api_key = os.getenv("SUNO_API_KEY")

        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN не задан")
        if not api_key:
            raise ValueError("SUNO_API_KEY не задан")

        return cls(
            telegram_bot_token=token,
            suno_api_key=api_key,
        )
