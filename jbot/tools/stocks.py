from jbot.tools.registry import tool


@tool
def get_stock_price(symbol: str):
    """
    Get the current stock price for a ticker symbol.

    Args:
        symbol: Stock ticker (e.g. 'AAPL', 'GOOGL', 'MSFT').
    """
    try:
        import yfinance as yf
    except ImportError:
        return "Error: yfinance is not installed. Run 'pip install yfinance'."
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
        currency = getattr(info, "currency", None) or "USD"
        if price is None:
            data = ticker.history(period="1d")
            if data.empty:
                return f"Could not retrieve price for {symbol}."
            price = float(data["Close"].iloc[-1])
        return {"symbol": symbol.upper(), "price": round(float(price), 4), "currency": currency}
    except Exception as exc:
        return f"Error fetching stock price: {exc}"
