from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


class CrawlItem(BaseModel):
    title: str | None = None
    summary: str | None = None
    source: str | None = None
    sourceType: str | None = None
    url: str
    publishedAt: str | None = None
    matchedKeyword: str | None = None
    searchProvider: str | None = None


class CrawlRequest(BaseModel):
    items: list[CrawlItem] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    searchMode: str = "any"
    location: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    maxResults: int = 40


app = FastAPI(title="Social Listening Crawlee Worker")
WORKER_TOKEN = os.getenv("CRAWLEE_WORKER_TOKEN", "").strip()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/crawl")
async def crawl(payload: CrawlRequest, x_worker_token: str | None = Header(default=None)) -> dict[str, Any]:
    if WORKER_TOKEN and x_worker_token != WORKER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid worker token")

    candidates = dedupe_items(payload.items)[: max(1, min(payload.maxResults, 100))]
    results: list[dict[str, Any]] = []

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=len(candidates))

    original_by_url = {item.url: item for item in candidates}

    @crawler.router.default_handler
    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
        original = original_by_url.get(context.request.url)
        if original is None:
            return

        soup = context.soup
        title = first_value(
            meta_content(soup, "og:title"),
            meta_content(soup, "twitter:title"),
            soup.title.string if soup.title else None,
            original.title,
        )
        summary = first_value(
            meta_content(soup, "og:description"),
            meta_content(soup, "twitter:description"),
            meta_content(soup, "description"),
            first_paragraph(soup),
            original.summary,
        )
        published_at = first_value(
            meta_content(soup, "article:published_time"),
            meta_content(soup, "article:modified_time"),
            meta_content(soup, "og:updated_time"),
            meta_content(soup, "date"),
            meta_content(soup, "dc.date"),
            original.publishedAt,
        )

        results.append(
            {
                "title": clean(title),
                "summary": clean(summary),
                "source": original.source or hostname(original.url),
                "sourceType": original.sourceType or "Crawler",
                "url": canonical_url(soup, original.url),
                "publishedAt": normalize_date(published_at),
                "matchedKeyword": original.matchedKeyword or "",
                "searchProvider": "crawlee_worker",
            }
        )

    await crawler.run([item.url for item in candidates])

    # Keep the response order close to the incoming discovery order.
    order = {item.url: index for index, item in enumerate(candidates)}
    results.sort(key=lambda item: order.get(item["url"], len(order)))
    return {"items": results}


def dedupe_items(items: list[CrawlItem]) -> list[CrawlItem]:
    seen: set[str] = set()
    output: list[CrawlItem] = []
    for item in items:
        url = item.url.strip()
        if not url or url in seen or not url.startswith(("http://", "https://")):
            continue
        seen.add(url)
        output.append(item)
    return output


def meta_content(soup: Any, name: str) -> str | None:
    selectors = [
        {"property": name},
        {"name": name},
        {"itemprop": name},
    ]
    for attrs in selectors:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return str(tag["content"])
    return None


def first_paragraph(soup: Any) -> str | None:
    for paragraph in soup.find_all("p"):
        text = clean(paragraph.get_text(" "))
        if len(text) >= 80:
            return text
    return None


def canonical_url(soup: Any, fallback: str) -> str:
    link = soup.find("link", rel=lambda value: value and "canonical" in value)
    href = link.get("href") if link else None
    return str(href).strip() if href else fallback


def first_value(*values: str | None) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def clean(value: str | None) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def normalize_date(value: str | None) -> str:
    text = clean(value)
    if not text:
        return datetime.now(timezone.utc).isoformat()
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).isoformat()
    except ValueError:
        return text


def hostname(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.removeprefix("www.") or "Nguon tin"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
