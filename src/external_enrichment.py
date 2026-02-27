"""
External enrichment module.

Lightweight, best-effort enrichment of vendor records using web/news search
and simple keyword-based heuristics for reputation, financial, and compliance
signals. Designed to be:
- Optional (gated by env flag EXTERNAL_ENRICHMENT_ENABLED)
- Resilient (timeouts, graceful failure)
- Cheap (small number of requests per vendor, truncated results)
"""

import os
import logging
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


# Basic config from environment
EXTERNAL_ENRICHMENT_ENABLED = os.getenv("EXTERNAL_ENRICHMENT_ENABLED", "false").lower() == "true"

# Optional API keys (not strictly required for the basic DuckDuckGo HTML fallback)
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "").strip()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()

USER_AGENT = (
    "Mozilla/5.0 (compatible; VendorAISearchBot/1.0; +https://example.com/bot)"
)

logger = logging.getLogger(__name__)


def is_enrichment_enabled() -> bool:
    """Return True if external enrichment is enabled."""
    return EXTERNAL_ENRICHMENT_ENABLED


def _http_get(url: str, params: Optional[dict] = None, timeout: int = 4) -> Optional[requests.Response]:
    """Small helper with UA + timeout and basic error handling."""
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp
        logger.warning("External GET %s returned status %s", url, resp.status_code)
    except Exception as e:  # pragma: no cover - safety net
        logger.warning("External GET failed for %s: %s", url, e)
    return None


def search_web(vendor_name: str, country: str, max_results: int = 5) -> List[Dict]:
    """
    Lightweight web search using DuckDuckGo HTML results as a fallback.

    Returns a list of dicts: {title, url, snippet, source}.
    """
    query = f'"{vendor_name}" {country}'

    # DuckDuckGo HTML endpoint (no JS required). This is best-effort and may change.
    resp = _http_get("https://duckduckgo.com/html/", params={"q": query})
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results: List[Dict] = []

    # DuckDuckGo HTML uses result__a / result__snippet classes typically,
    # but we keep parsing defensive.
    for result in soup.select("div.result")[:max_results]:
        link = result.select_one("a.result__a")
        snippet_el = result.select_one("a.result__snippet") or result.select_one("div.result__snippet")
        if not link:
            continue
        title = link.get_text(strip=True)
        url = link.get("href") or ""
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        if not url:
            continue
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": "duckduckgo",
            }
        )

    return results


def _classify_sentiment_and_flags(items: List[Dict]) -> Dict:
    """
    Very simple, keyword-based sentiment + flag detection over titles/snippets.
    """
    text_blobs = []
    for item in items:
        text_blobs.append((item.get("title", "") + " " + item.get("snippet", "")).lower())

    positive_keywords = ["award", "leader", "recognized", "best", "win", "won"]
    negative_financial = ["bankrupt", "insolvency", "liquidation", "winding up", "wound up"]
    negative_compliance = ["fine", "penalty", "breach", "data leak", "violation", "sanction"]

    positive_hits: List[str] = []
    neg_fin_hits: List[str] = []
    neg_comp_hits: List[str] = []

    for blob in text_blobs:
        for kw in positive_keywords:
            if kw in blob and kw not in positive_hits:
                positive_hits.append(kw)
        for kw in negative_financial:
            if kw in blob and kw not in neg_fin_hits:
                neg_fin_hits.append(kw)
        for kw in negative_compliance:
            if kw in blob and kw not in neg_comp_hits:
                neg_comp_hits.append(kw)

    # Simple overall sentiment flag
    if neg_fin_hits or neg_comp_hits:
        overall = "negative"
    elif positive_hits:
        overall = "positive"
    else:
        overall = "neutral"

    return {
        "overall_sentiment": overall,
        "positive_signals": positive_hits,
        "financial_red_flags": neg_fin_hits,
        "compliance_red_flags": neg_comp_hits,
    }


def search_news(vendor_name: str, country: str, max_results: int = 5) -> List[Dict]:
    """
    Placeholder for a news API integration.

    If NEWS_API_KEY is not configured, returns an empty list.
    The shape matches: {headline, source, url, published_at, sentiment}.
    """
    if not NEWS_API_KEY:
        return []

    # This is intentionally a stub – the actual endpoint depends on chosen provider.
    # We keep the structure so that wiring into the UI/LLM is ready.
    # Example pseudo-implementation:
    #
    # resp = _http_get(
    #     "https://gnews.io/api/v4/search",
    #     params={"q": f'"{vendor_name}" {country}', "token": NEWS_API_KEY, "max": max_results},
    # )
    # if not resp:
    #     return []
    # data = resp.json()
    # ...
    #
    return []


def check_sanctions(vendor_name: str) -> Dict:
    """
    Very simple sanctions / regulatory placeholder.

    For a free MVP, we default to 'not sanctioned' unless you later
    wire this to a local sanctions dataset.
    """
    return {
        "sanctioned": False,
        "sanctions_sources": [],
        "regulatory_issues": [],
    }


def lookup_registry(vendor_name: str, country: str) -> Dict:
    """
    Best-effort registry-like lookup using web search heuristics.

    For Malaysia/Singapore, we look for .gov.* domains mentioning the vendor.
    This is heuristic only and may often be empty.
    """
    country_lower = country.upper()
    results = search_web(f"{vendor_name} company registration", country)
    registry_candidates: List[Dict] = []

    for item in results:
        url = item.get("url", "")
        if ".gov.my" in url or ".gov.sg" in url or "ssm.com.my" in url or "acra.gov.sg" in url:
            registry_candidates.append(item)

    if not registry_candidates:
        return {}

    top = registry_candidates[0]
    text = (top.get("title", "") + " " + top.get("snippet", "")).lower()

    status = None
    if "wound up" in text or "winding up" in text or "struck off" in text:
        status = "wound_up"
    elif "dissolved" in text or "inactive" in text:
        status = "inactive"
    elif "active" in text or "existing" in text:
        status = "active"

    return {
        "company_status": status,
        "registry_source_url": top.get("url"),
        "registry_snippet": top.get("snippet"),
    }


def build_enrichment_profile(vendor_profile: Dict) -> Dict:
    """
    High-level orchestrator. Accepts a simple vendor profile dict:
    {
      'vendor_id': str,
      'vendor_name': str,
      'country': str,
      'city': str | None,
      'industry': str | None
    }
    """
    if not EXTERNAL_ENRICHMENT_ENABLED:
        return {}

    vendor_name = vendor_profile.get("vendor_name", "")
    country = vendor_profile.get("country", "") or ""

    if not vendor_name:
        return {}

    # 1) Web search
    web_items = search_web(vendor_name, country)
    sentiment = _classify_sentiment_and_flags(web_items) if web_items else {
        "overall_sentiment": "unknown",
        "positive_signals": [],
        "financial_red_flags": [],
        "compliance_red_flags": [],
    }

    # 2) News (optional stub)
    news_items = search_news(vendor_name, country)

    # 3) Sanctions (stub)
    sanctions = check_sanctions(vendor_name)

    # 4) Registry heuristic
    registry_info = lookup_registry(vendor_name, country)

    # Build normalized enrichment dict
    enrichment: Dict = {
        "reputation": {
            "summary": sentiment.get("overall_sentiment", "unknown"),
            "negative_signals": sentiment.get("financial_red_flags", [])
            + sentiment.get("compliance_red_flags", []),
            "positive_signals": sentiment.get("positive_signals", []),
            "news": [
                {
                    "headline": item.get("title", ""),
                    "source": item.get("source", "web"),
                    "url": item.get("url", ""),
                    "published_at": item.get("published_at", ""),
                    "sentiment": "unknown",
                }
                for item in news_items[:5]
            ],
            "web_samples": web_items[:5],
        },
        "financial_flags": {
            "red_flags": sentiment.get("financial_red_flags", []),
            "notes": "",
        },
        "compliance_flags": {
            "sanctioned": sanctions.get("sanctioned", False),
            "sanctions_sources": sanctions.get("sanctions_sources", []),
            "regulatory_issues": sanctions.get("regulatory_issues", []),
        },
        "registry": registry_info,
        "sources": [],
    }

    for item in web_items[:3]:
        enrichment["sources"].append(
            {"type": "web_search", "url": item.get("url", ""), "label": item.get("title", "")}
        )
    for item in news_items[:3]:
        enrichment["sources"].append(
            {"type": "news", "url": item.get("url", ""), "label": item.get("headline", "")}
        )
    if registry_info.get("registry_source_url"):
        enrichment["sources"].append(
            {
                "type": "registry",
                "url": registry_info["registry_source_url"],
                "label": "Company registry result",
            }
        )

    return enrichment


