from __future__ import annotations

from live_captions.config import AppConfig
from live_captions.errors import ConfigError
from live_captions.translate.engines import DeepLTranslator, LibreTranslator, OpenAITranslator
from live_captions.translate.local_mt import LocalEnZhTranslator


def build_translator(config: AppConfig):
    if config.translator == "local":
        return LocalEnZhTranslator(cpu_threads=config.cpu_threads)
    if config.translator == "deepl":
        if not config.deepl_key:
            raise ConfigError("CAPTIONS_TRANSLATOR=deepl，但沒有設定 DEEPL_API_KEY。")
        return DeepLTranslator(config.deepl_key)
    if config.translator == "openai":
        if not config.openai_key:
            raise ConfigError("CAPTIONS_TRANSLATOR=openai，但沒有設定 OPENAI_API_KEY。")
        return OpenAITranslator(config.openai_key, config.openai_model, config.openai_base_url)
    if config.translator == "libre":
        if not config.libre_url:
            raise ConfigError("CAPTIONS_TRANSLATOR=libre，但沒有設定 LIBRETRANSLATE_URL。")
        return LibreTranslator(config.libre_url, config.libre_key)
    raise ConfigError("CAPTIONS_TRANSLATOR 請設為 local、deepl、openai 或 libre。")
