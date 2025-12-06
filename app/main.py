from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
import json
import csv
import io
from typing import Dict, List
from datetime import datetime, timezone

from app.schemas import ScrapeRequest, ScrapeResponse
from app.scraper import build_result
from app.cache import get_cached_result, cache_result

app = FastAPI(
    title="Universal Website Scraper",
    description="A modern web scraper with beautiful UI",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Get the directory where main.py is located
current_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

# In-memory storage for recent scrapes
recent_scrapes: List[Dict] = []
MAX_RECENT_SCRAPES = 10


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/stats")
async def get_stats():
    """Get scraping statistics"""
    return {
        "total_scrapes": len(recent_scrapes),
        "success_rate": sum(1 for s in recent_scrapes if not s.get("errors", [])) / len(recent_scrapes) if recent_scrapes else 0,
        "recent_scrapes": recent_scrapes[-5:] if recent_scrapes else []
    }


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    url = req.url.strip()
    
    # Validate URL
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Only http(s) URLs are supported")
    
    # Check cache first
    cached = get_cached_result(url)
    if cached:
        return ScrapeResponse(result=cached)
    
    try:
        result = build_result(url)
        
        # Cache the result
        background_tasks.add_task(cache_result, url, result)
        
        # Add to recent scrapes
        recent_scrapes.append({
            "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sections_count": len(result.sections),
            "strategy": result.meta.strategy or "unknown",
            "errors": len(result.errors)
        })
        
        # Keep only recent scrapes
        if len(recent_scrapes) > MAX_RECENT_SCRAPES:
            recent_scrapes.pop(0)
        
        return ScrapeResponse(result=result)
    
    except Exception as e:
        from app.schemas import Meta, SectionContent, Section, Interactions, ErrorItem, ScrapeResult
        
        err = ErrorItem(message=str(e), phase="unknown")
        empty_meta = Meta(
            title="",
            description="",
            language="",
            canonical=None,
            strategy=None,
        )
        dummy_content = SectionContent(
            headings=[],
            text="",
            links=[],
            images=[],
            lists=[],
            tables=[],
        )
        dummy_section = Section(
            id="section-0",
            type="unknown",
            label="Empty",
            sourceUrl=url,
            content=dummy_content,
            rawHtml="",
            truncated=False,
        )
        interactions = Interactions(clicks=[], scrolls=0, pages=[url])
        result = ScrapeResult(
            url=url,
            scrapedAt=datetime.now(timezone.utc),
            meta=empty_meta,
            sections=[dummy_section],
            interactions=interactions,
            errors=[err],
        )
        return ScrapeResponse(result=result)


@app.post("/export/json")
async def export_json(data: dict):
    """Export data as JSON"""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
    return StreamingResponse(
        io.StringIO(json_str),
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=scrape-result.json"
        }
    )


@app.post("/export/csv")
async def export_csv(data: dict):
    """Export sections as CSV"""
    sections = data.get("result", {}).get("sections", [])
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "ID", "Type", "Label", "Text Length", 
        "Headings Count", "Links Count", "Images Count"
    ])
    
    # Write data
    for section in sections:
        writer.writerow([
            section.get("id", ""),
            section.get("type", ""),
            section.get("label", ""),
            len(section.get("content", {}).get("text", "")),
            len(section.get("content", {}).get("headings", [])),
            len(section.get("content", {}).get("links", [])),
            len(section.get("content", {}).get("images", []))
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sections.csv"
        }
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard")
async def dashboard(request: Request):
    """Dashboard page with statistics"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "recent_scrapes": recent_scrapes[-5:][::-1] if recent_scrapes else [],
        "total_scrapes": len(recent_scrapes)
    })


# Error handlers
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)


@app.exception_handler(500)
async def internal_exception_handler(request: Request, exc: Exception):
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)