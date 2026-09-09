import re

import requests

from jbot.config import PAXSENIX_API_KEY, PAXSENIX_BASE_URL, TINYFISH_KEY
from jbot.tools.registry import tool


@tool
def get_weather(location: str):
    """
    Get the current weather for a location using Open-Meteo.

    Args:
        location: Place name requested by the user (city, region, etc.).
    """
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": location, "count": 1, "language": "en", "format": "json"},
        timeout=15,
    )
    geo.raise_for_status()
    data = geo.json()
    results = data.get("results") or []
    if not results:
        return f"Could not find location '{location}'."
    place = results[0]
    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m,weather_code",
        },
        timeout=15,
    )
    weather.raise_for_status()
    current = weather.json().get("current") or {}
    name = place.get("name", location)
    country = place.get("country_code", "")
    return {
        "location": f"{name}, {country}".strip(", "),
        "temperature_c": current.get("temperature_2m"),
        "wind_kmh": current.get("wind_speed_10m"),
        "humidity": current.get("relative_humidity_2m"),
        "weather_code": current.get("weather_code"),
    }


def _paxsenix_search(query: str, max_content_chars: int = 600):
    headers = {
        "Authorization": f"Bearer {PAXSENIX_API_KEY}",
        "User-Agent": "jbot-agent",
    }
    last_error = None
    for engine in ("turboseek", "duckassist", "felo"):
        try:
            response = requests.get(
                f"{PAXSENIX_BASE_URL}/ai-search/{engine}",
                headers=headers,
                params={"text": query},
                timeout=30,
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            continue
        if response.status_code != 200:
            last_error = f"{engine} HTTP {response.status_code}: {response.text[:200]}"
            continue
        try:
            body = response.json()
        except ValueError:
            last_error = f"{engine} returned non-JSON"
            continue
        if not body.get("ok"):
            last_error = body.get("message") or f"{engine} failed"
            continue
        sources = []
        for item in body.get("sources") or []:
            if "article" in item:
                article = item.get("article") or {}
                title = article.get("text") or ""
                link = article.get("link") or ""
                content = ""
            else:
                title = item.get("title") or ""
                link = item.get("url") or ""
                content = item.get("content") or ""
            trimmed = content[:max_content_chars]
            if len(content) > max_content_chars:
                trimmed += "..."
            sources.append({"title": title, "url": link, "content": trimmed})
        answer = re.sub(r"<[^>]+>", " ", body.get("answer") or "")
        answer = re.sub(r"\s+", " ", answer).strip()
        return {
            "ok": True,
            "query": query,
            "engine": engine,
            "answer": answer,
            "sources": sources,
        }
    return {
        "ok": False,
        "query": query,
        "answer": "",
        "sources": [],
        "engine": None,
        "error": last_error or "all PaxSenix search engines failed",
    }


@tool
def web_search(query: str):
    """
    Search the web via PaxSenix AI-search and return an answer plus sources.

    Args:
        query: Search query from the user.
    """
    result = _paxsenix_search(query)
    if result.get("ok"):
        return result
    if TINYFISH_KEY:
        headers = {"X-API-Key": TINYFISH_KEY}
        response = requests.get(
            "https://agent.tinyfish.ai/v1/search",
            headers=headers,
            params={"query": query},
            timeout=20,
        )
        if response.status_code != 200:
            return {
                "error": f"Search API error: {response.status_code}",
                "detail": response.text[:300],
                "paxsenix": result,
            }
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            return {"query": query, "results": [], "note": "No results."}
        first_url = results[0].get("url")
        fetch = requests.post(
            "https://agent.tinyfish.ai/v1/fetch",
            headers=headers,
            json={"urls": [first_url]},
            timeout=30,
        )
        return {
            "query": query,
            "results": results[:5],
            "top_page": fetch.json() if fetch.status_code == 200 else None,
        }
    return result


@tool
def web_fetch(url: str):
    """
    Fetch a public http(s) page and return readable text.

    Args:
        url: Full URL beginning with http:// or https://.
    """
    target = (url or "").strip()
    if not target.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}
    try:
        response = requests.get(
            target,
            timeout=20,
            headers={"User-Agent": "jbot-agent"},
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return {"error": str(exc)}
    if response.status_code != 200:
        return {"error": f"HTTP {response.status_code}", "url": target}
    text = response.text or ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 4000:
        text = text[:4000] + "..."
    return {"url": target, "status": response.status_code, "text": text}
