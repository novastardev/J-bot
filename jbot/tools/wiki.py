from jbot.tools.registry import tool


@tool
def wikipedia_summary(query: str, sentences: int = 3):
    """
    Get a short summary from Wikipedia.

    Args:
        query: Topic to search for.
        sentences: Number of sentences to return (default 3).
    """
    try:
        import wikipedia
    except ImportError:
        return "Error: wikipedia library not installed. Run 'pip install wikipedia'."
    try:
        wikipedia.set_lang("en")
        return wikipedia.summary(query, sentences=int(sentences) if sentences else 3, auto_suggest=True)
    except wikipedia.exceptions.DisambiguationError as exc:
        options = ", ".join(exc.options[:8])
        return f"Disambiguation. Try one of: {options}"
    except wikipedia.exceptions.PageError:
        return f"No Wikipedia page found for '{query}'."
    except Exception as exc:
        return f"Error: {exc}"
