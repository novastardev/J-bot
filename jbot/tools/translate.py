import requests

from jbot.tools.registry import tool


@tool
def translate_text(text: str, target_lang: str, source_lang: str = "auto"):
    """
    Translate text using LibreTranslate (no API key required).

    Args:
        text: The text to translate.
        target_lang: Target language code (e.g. 'es', 'fr', 'de', 'zh', 'ja').
        source_lang: Source language code or 'auto'.
    """
    payload = {"q": text, "source": source_lang, "target": target_lang, "format": "text"}
    endpoints = [
        "https://libretranslate.de/translate",
        "https://translate.argosopentech.com/translate",
        "https://libretranslate.com/translate",
    ]
    last_error = None
    for url in endpoints:
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                return response.json().get("translatedText", "Translation failed.")
            last_error = f"{response.status_code} from {url}"
        except Exception as exc:
            last_error = str(exc)
    return f"Translation error: {last_error}"
