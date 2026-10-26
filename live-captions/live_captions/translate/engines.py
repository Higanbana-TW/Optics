from __future__ import annotations

import httpx

from live_captions.errors import CaptionsError

OPENAI_SYSTEM_PROMPT = (
    "You translate live English meeting captions into Traditional Chinese used in Taiwan. "
    "Return only the translation. Do not add notes, quotes, or the original English. "
    "Use Taiwan terminology such as 軟體, 網路, 影片, 資訊, 預設, and 程式. "
    "Keep personal names, product names, and numbers unchanged. "
    "Stay concise enough for one subtitle."
)


def deepl_endpoint(api_key: str) -> str:
    host = "api-free.deepl.com" if api_key.endswith(":fx") else "api.deepl.com"
    return f"https://{host}/v2/translate"


def http_error(service: str, status: int) -> CaptionsError:
    if status == 456 and service == "DeepL":
        return CaptionsError("DeepL 額度已用完（HTTP 456）。")
    if status in {401, 403}:
        return CaptionsError(f"{service} 拒絕了 API 金鑰（HTTP {status}）。")
    return CaptionsError(f"{service} 翻譯失敗（HTTP {status}）。")


class _HttpTranslator:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=8.0)

    def warmup(self, on_status=None) -> None:
        return None


class DeepLTranslator(_HttpTranslator):
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        super().__init__(client)
        self.api_key = api_key

    def translate(self, text: str) -> str:
        response = self.client.post(
            deepl_endpoint(self.api_key),
            json={"text": [text], "source_lang": "EN", "target_lang": "ZH-HANT"},
            headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
        )
        if response.status_code >= 400:
            raise http_error("DeepL", response.status_code)
        try:
            payload = response.json()
            return str(payload["translations"][0]["text"]).strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise CaptionsError("DeepL 回傳的內容無法讀取。") from exc


class OpenAITranslator(_HttpTranslator):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(client)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def translate(self, text: str) -> str:
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
        )
        if response.status_code >= 400:
            raise http_error("OpenAI", response.status_code)
        try:
            payload = response.json()
            return str(payload["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise CaptionsError("OpenAI 回傳的內容無法讀取。") from exc


class LibreTranslator(_HttpTranslator):
    def __init__(self, url: str, api_key: str | None = None, client: httpx.Client | None = None) -> None:
        super().__init__(client)
        self.url = url.rstrip("/")
        self.api_key = api_key

    def translate(self, text: str) -> str:
        body = {"q": text, "source": "en", "target": "zh", "format": "text"}
        if self.api_key:
            body["api_key"] = self.api_key
        response = self.client.post(f"{self.url}/translate", json=body)
        if response.status_code >= 400:
            raise http_error("LibreTranslate", response.status_code)
        try:
            return str(response.json()["translatedText"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise CaptionsError("LibreTranslate 回傳的內容無法讀取。") from exc
