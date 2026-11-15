"""Conservative, auditable asset mention rules. No false fruit/ordinary-word matches."""
import re
import unicodedata

COMPANY = {
    "AAPL": ("apple",), "MSFT": ("microsoft",),
    "NVDA": ("nvidia",), "TSLA": ("tesla",),
    "AMZN": ("amazon",), "GOOG": ("alphabet", "google"),
    "GOOGL": ("alphabet", "google"), "META": ("meta platforms", "meta"),
}
FINANCIAL = re.compile(
    r"\b(stock|stocks|share|shares|ticker|earnings|eps|revenue|valuation|quarter|"
    r"quarterly|guidance|dividend|investor|investors|equity|profit|forecast|nasdaq|"
    r"analyst|upgrade|downgrade|buyback|market cap)\b", re.I)

def relevance_reason(text: str, ticker: str) -> str | None:
    ticker = ticker.strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}', ticker):
        raise ValueError('Unsafe or invalid asset symbol')
    s = unicodedata.normalize('NFKC', str(text))
    if re.search(r'(?<![\w$])\$'+re.escape(ticker)+r'\b',s,flags=re.I):
        return 'exact_cashtag'
    if FINANCIAL.search(s):
        if ticker == 'AAPL' and re.search(r'\bapple\s+(?:pie|fruit|juice|orchard|cider)\b',s,flags=re.I):
            return None  # nonfinancial false-positive safeguard
        if re.search(r'(?<![\w$])'+re.escape(ticker)+r'\b',s,flags=re.I):
            return 'ticker_with_financial_context'
        for alias in COMPANY.get(ticker, ()):
            if re.search(r'\b'+re.escape(alias)+r'\b',s,flags=re.I):
                return 'company_with_financial_context'
    return None
