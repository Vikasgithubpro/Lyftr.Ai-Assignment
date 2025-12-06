from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel


class ScrapeRequest(BaseModel):
    url: str


class Link(BaseModel):
    text: str
    href: str


class Image(BaseModel):
    src: str
    alt: str


class SectionContent(BaseModel):
    headings: List[str]
    text: str
    links: List[Link]
    images: List[Image]
    lists: List[List[str]]
    tables: List[Any]


class Section(BaseModel):
    id: str
    type: str
    label: str
    sourceUrl: str
    content: SectionContent
    rawHtml: str
    truncated: bool


class Meta(BaseModel):
    title: str
    description: str
    language: str
    canonical: Optional[str] = None
    # Optional: indicate strategy for debugging
    strategy: Optional[str] = None  # "static" | "js" | "static+js"


class Interactions(BaseModel):
    clicks: List[str]
    scrolls: int
    pages: List[str]


class ErrorItem(BaseModel):
    message: str
    phase: str


class ScrapeResult(BaseModel):
    url: str
    scrapedAt: datetime
    meta: Meta
    sections: List[Section]
    interactions: Interactions
    errors: List[ErrorItem]


class ScrapeResponse(BaseModel):
    result: ScrapeResult