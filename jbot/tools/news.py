import requests

from jbot.config import NEWS_API_KEY
from jbot.tools.registry import tool


@tool
def get_news(country: str = "us", category: str = ""):
    """
    Get top news headlines.

    Args:
        country: 2-letter country code (default: us).
        category: Optional category: business, entertainment, general, health, science, sports, technology.
    """
    if not NEWS_API_KEY:
        hn = requests.get("https://hn.algolia.com/api/v1/search?tags=front_page", timeout=15)
        if hn.status_code != 200:
            return "News API key not set. Add NEWS_API_KEY in .env (https://newsapi.org/) or try again later."
        hits = hn.json().get("hits") or []
        return [
            {"title": item.get("title"), "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}", "source": "Hacker News"}
            for item in hits[:8]
        ]

    params = {"country": country, "apiKey": NEWS_API_KEY}
    if category:
        params["category"] = category
    response = requests.get("https://newsapi.org/v2/top-headlines", params=params, timeout=15)
    if response.status_code != 200:
        return f"News API error: {response.status_code}"
    articles = response.json().get("articles") or []
    if not articles:
        return "No news found."
    return [
        {"title": article.get("title"), "description": article.get("description"), "url": article.get("url")}
        for article in articles[:8]
    ]
