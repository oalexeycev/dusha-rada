"""Обёртка над SunoAPI.org для генерации музыки."""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SongResult:
    """Результат генерации одной песни."""

    id: str
    title: str
    audio_url: str
    prompt: str | None = None
    tags: str | None = None
    duration: float | None = None


@dataclass
class GenerationResult:
    """Результат полной генерации (2 песни)."""

    task_id: str
    songs: list[SongResult]
    status: str


class SunoAPIError(Exception):
    """Ошибка SunoAPI."""

    def __init__(self, message: str, code: int | None = None):
        self.code = code
        super().__init__(message)


class SunoAPI:
    """Клиент для SunoAPI.org."""

    def __init__(self, api_key: str, base_url: str = "https://api.sunoapi.org"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        style: str = "",
        title: str = "Generated Song",
        instrumental: bool = False,
        model: str = "V5",
    ) -> str:
        """
        Запустить генерацию музыки.
        Возвращает task_id для последующего поллинга.
        """
        # Используем non-custom mode для простоты: только prompt
        # customMode: false — lyrics генерируются автоматически
        payload: dict[str, Any] = {
            "customMode": False,
            "instrumental": instrumental,
            "model": model,
            "prompt": prompt[:500],  # лимит для non-custom mode
            "callBackUrl": "https://example.com/callback",  # не используем, поллим
        }

        if style or title:
            # Если указаны style/title — переключаемся в custom mode
            payload["customMode"] = True
            payload["style"] = style or "Pop"
            payload["title"] = title[:80]
            payload["prompt"] = prompt[:5000]

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/generate",
                headers=self._headers,
                json=payload,
            )

        data = resp.json()
        if resp.status_code != 200 or data.get("code") != 200:
            msg = data.get("msg", resp.text) or f"HTTP {resp.status_code}"
            code = data.get("code")
            logger.error("SunoAPI generate failed: %s (code=%s)", msg, code)
            raise SunoAPIError(msg, code)

        task_id = data.get("data", {}).get("taskId")
        if not task_id:
            raise SunoAPIError("Нет taskId в ответе API")

        logger.info("Generation started, task_id=%s", task_id)
        return task_id

    async def get_status(self, task_id: str) -> GenerationResult:
        """Получить статус генерации по task_id."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/generate/record-info",
                headers=self._headers,
                params={"taskId": task_id},
            )

        data = resp.json()
        if resp.status_code != 200 or data.get("code") != 200:
            msg = data.get("msg", resp.text) or f"HTTP {resp.status_code}"
            raise SunoAPIError(msg, data.get("code"))

        result = data.get("data", {})
        status = result.get("status", "").upper()

        # Финальные статусы: SUCCESS или ошибки
        failed_statuses = {
            "CREATE_TASK_FAILED",
            "GENERATE_AUDIO_FAILED",
            "CALLBACK_EXCEPTION",
            "SENSITIVE_WORD_ERROR",
        }

        if status in failed_statuses:
            err_msg = result.get("errorMessage") or result.get("errorCode") or status
            raise SunoAPIError(f"Генерация не удалась: {err_msg}")

        songs: list[SongResult] = []
        response = result.get("response") or {}
        suno_data = response.get("sunoData") or []
        for item in suno_data:
            songs.append(
                SongResult(
                    id=item.get("id", ""),
                    title=item.get("title", "Unknown"),
                    audio_url=item.get("audioUrl") or item.get("audio_url") or item.get("streamAudioUrl") or "",
                    prompt=item.get("prompt"),
                    tags=item.get("tags"),
                    duration=item.get("duration"),
                )
            )

        return GenerationResult(task_id=task_id, songs=songs, status=status)

    async def get_balance(self) -> int:
        """Получить остаток кредитов."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/generate/credit",
                headers=self._headers,
            )

        data = resp.json()
        if resp.status_code != 200 or data.get("code") != 200:
            msg = data.get("msg", resp.text) or f"HTTP {resp.status_code}"
            raise SunoAPIError(msg, data.get("code"))

        return int(data.get("data", 0))
