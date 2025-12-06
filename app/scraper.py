import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Tuple, Any, Optional
from urllib.parse import urljoin, urlparse
import time

import httpx
from bs4 import BeautifulSoup
from selectolax.parser import HTMLParser as SelectolaxParser

from app.schemas import (
    Meta,
    SectionContent,
    Section,
    Interactions,
    ErrorItem,
    ScrapeResult,
)

# Configuration
STATIC_TIMEOUT = 15.0
JS_TIMEOUT = 30000  # ms
MAX_HTML_CHARS = 4000
MAX_SECTIONS = 50
MAX_LINKS_PER_SECTION = 100


@dataclass
class ScrapeContext:
    url: str
    pages: List[str] = field(default_factory=list)
    clicks: List[str] = field(default_factory=list)
    scrolls: int = 0
    errors: List[ErrorItem] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    strategy: str = "static"


def is_valid_url(url: str) -> bool:
    """Check if URL is valid and safe to scrape"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False


def normalize_url(url: str) -> str:
    """Normalize URL for caching"""
    url = url.lower().strip()
    if url.endswith('/'):
        url = url[:-1]
    return url


def fetch_static_html(url: str, ctx: ScrapeContext) -> Tuple[str, httpx.Response]:
    """Fetch HTML using HTTPX with enhanced error handling"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
    }
    
    try:
        with httpx.Client(
            timeout=STATIC_TIMEOUT,
            follow_redirects=True,
            headers=headers,
            verify=False  # For development only
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            
            final_url = str(resp.url)
            if final_url not in ctx.pages:
                ctx.pages.append(final_url)
            
            return resp.text, resp
    
    except httpx.TimeoutException:
        ctx.errors.append(ErrorItem(message="Request timeout", phase="fetch"))
    except httpx.HTTPStatusError as e:
        ctx.errors.append(ErrorItem(message=f"HTTP {e.response.status_code}", phase="fetch"))
    except Exception as e:
        ctx.errors.append(ErrorItem(message=str(e), phase="fetch"))
    
    return "", None


def extract_meta(soup: BeautifulSoup, url: str) -> Meta:
    """Extract enhanced metadata from HTML"""
    # Title
    title_tag = soup.find("title")
    og_title = soup.find("meta", property="og:title")
    twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
    
    title = ""
    for source in [og_title, twitter_title, title_tag]:
        if source and source.get("content" if source.name == "meta" else None):
            title = source["content" if source.name == "meta" else "text"].strip()
            if title:
                break
    
    # Description
    desc_tag = soup.find("meta", attrs={"name": "description"})
    og_desc = soup.find("meta", property="og:description")
    twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
    
    description = ""
    for source in [og_desc, twitter_desc, desc_tag]:
        if source and source.get("content"):
            description = source["content"].strip()
            if description:
                break
    
    # Language
    html_tag = soup.find("html")
    language = html_tag.get("lang", "").strip() if html_tag else ""
    if not language:
        # Try to detect from content
        text = soup.get_text()[:1000].lower()
        if any(word in text for word in ['the', 'and', 'for', 'with']):
            language = "en"
        elif any(word in text for word in ['el', 'la', 'de', 'y']):
            language = "es"
        elif any(word in text for word in ['le', 'la', 'de', 'et']):
            language = "fr"
    
    # Canonical
    canonical_link = soup.find("link", rel="canonical")
    canonical = None
    if canonical_link and canonical_link.get("href"):
        canonical = canonical_link["href"].strip()
        if canonical and not canonical.startswith("http"):
            canonical = urljoin(url, canonical)
    
    return Meta(
        title=title or "",
        description=description or "",
        language=language or "",
        canonical=canonical,
        strategy=None,
    )


def is_noise_section(tag) -> bool:
    """Enhanced noise detection with more patterns"""
    if not tag:
        return True
    
    classes = " ".join(tag.get("class", [])).lower()
    id_ = (tag.get("id") or "").lower()
    text = tag.get_text().lower()
    
    # Common noise patterns
    noise_patterns = [
        # Cookie/consent banners
        "cookie", "consent", "gdpr", "privacy-banner", "cookie-notice",
        # Popups/modals
        "modal", "popup", "overlay", "lightbox", "dialog",
        # Newsletter/subscription
        "newsletter", "subscribe", "signup", "email-capture", "mailing-list",
        # Ads
        "advertisement", "ad-container", "banner-ad", "adsense", "adslot",
        # Social/share
        "social-share", "share-buttons", "social-media", "follow-us",
        # Chat/help widgets
        "chat-widget", "help-widget", "intercom", "zendesk", "livechat",
        # Accessibility
        "skip-link", "sr-only", "visually-hidden", "screen-reader",
        # Navigation/utility
        "breadcrumb", "pagination", "toolbar", "sidebar", "widget",
        # Comments
        "comments", "comment-section", "disqus",
        # Tracking/analytics
        "analytics", "tracking", "pixel", "beacon",
        # Empty/utility sections
        "hidden", "invisible", "spacer", "clearfix", "placeholder"
    ]
    
    # Check for patterns
    for pattern in noise_patterns:
        if pattern in classes or pattern in id_:
            return True
    
    # Check for empty or very small sections
    text_length = len(tag.get_text(strip=True))
    if text_length < 20 and len(tag.find_all(['img', 'a', 'button', 'input', 'form'])) == 0:
        return True
    
    # Check for hidden elements
    style = tag.get("style", "").lower()
    if "display: none" in style or "visibility: hidden" in style:
        return True
    
    return False


def derive_section_type(tag, content: SectionContent) -> str:
    """Enhanced section type detection"""
    name = tag.name.lower()
    classes = " ".join(tag.get("class", [])).lower()
    id_ = (tag.get("id") or "").lower()
    
    # Hero/Banner
    if name == "header" or "hero" in classes or "hero" in id_ or "banner" in classes:
        return "hero"
    
    # Navigation
    if name == "nav" or "navigation" in classes or "navbar" in classes or "menu" in classes:
        return "nav"
    
    # Footer
    if name == "footer" or "footer" in classes:
        return "footer"
    
    # Pricing
    if "pricing" in classes or "pricing" in id_ or "price" in classes:
        return "pricing"
    
    # FAQ
    if "faq" in classes or "faq" in id_ or "question" in classes or "answer" in classes:
        return "faq"
    
    # Grid/Grid layout
    if "grid" in classes or "row" in classes or "column" in classes or "cols" in classes:
        return "grid"
    
    # List
    if tag.find(["ul", "ol"]):
        return "list"
    
    # Table
    if tag.find("table"):
        return "table"
    
    # Form
    if tag.find("form") or tag.find("input") or tag.find("button[type='submit']"):
        return "form"
    
    # Article/Blog post
    if name == "article" or "article" in classes or "post" in classes or "blog" in classes:
        return "article"
    
    # Sidebar
    if "sidebar" in classes or "aside" in classes:
        return "sidebar"
    
    # Card
    if "card" in classes or "panel" in classes or "box" in classes:
        return "card"
    
    # Check content patterns
    if len(content.headings) >= 2:
        return "content"
    
    if len(content.links) > 5:
        return "nav"
    
    return "section"


def derive_label(tag, section_type: str, content: SectionContent) -> str:
    """Generate human-readable label with fallbacks"""
    # Try aria-label
    aria_label = tag.get("aria-label")
    if aria_label and aria_label.strip():
        return aria_label.strip()[:100]
    
    # Try title attribute
    title = tag.get("title")
    if title and title.strip():
        return title.strip()[:100]
    
    # Use first heading
    if content.headings:
        return content.headings[0][:80]
    
    # Type-specific defaults
    type_labels = {
        "hero": "Hero Section",
        "nav": "Navigation",
        "footer": "Footer",
        "pricing": "Pricing",
        "faq": "FAQ",
        "grid": "Grid Layout",
        "list": "List",
        "table": "Table",
        "form": "Form",
        "article": "Article",
        "sidebar": "Sidebar",
        "card": "Card",
    }
    
    if section_type in type_labels:
        return type_labels[section_type]
    
    # Generate from text content
    words = content.text.strip().split()
    if words:
        # Take first 5-7 words
        label_words = words[:min(7, len(words))]
        label = " ".join(label_words)
        if len(label) > 60:
            label = label[:57] + "..."
        return label
    
    # Fallback
    return f"{section_type.capitalize()} Section"


def extract_section_content(tag, base_url: str) -> SectionContent:
    """Extract structured content with limits"""
    # Headings
    heading_tags = tag.select("h1, h2, h3, h4, h5, h6")
    headings = [h.get_text(" ", strip=True) for h in heading_tags[:10] if h.get_text(strip=True)]
    
    # Clean up for text extraction
    for s in tag(["script", "style", "noscript", "svg", "iframe"]):
        s.decompose()
    
    # Text content
    text = tag.get_text(" ", strip=True)
    
    # Links
    links = []
    link_elements = tag.find_all("a", href=True)[:MAX_LINKS_PER_SECTION]
    for a in link_elements:
        href = a["href"].strip()
        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
            continue
        
        href_abs = urljoin(base_url, href)
        link_text = a.get_text(" ", strip=True) or href_abs
        if len(link_text) > 100:
            link_text = link_text[:97] + "..."
        
        links.append({"text": link_text, "href": href_abs})
    
    # Images
    images = []
    img_elements = tag.find_all("img", src=True)[:50]
    for img in img_elements:
        src = img["src"].strip()
        if not src or src.startswith('data:'):
            continue
        
        src_abs = urljoin(base_url, src)
        alt = img.get("alt", "").strip() or img.get("title", "").strip()
        if len(alt) > 200:
            alt = alt[:197] + "..."
        
        images.append({"src": src_abs, "alt": alt})
    
    # Lists
    lists = []
    list_elements = tag.find_all(["ul", "ol"])[:10]
    for lst in list_elements:
        items = []
        for li in lst.find_all("li")[:50]:
            txt = li.get_text(" ", strip=True)
            if txt:
                items.append(txt)
        if items:
            lists.append(items)
    
    # Tables
    tables = []
    table_elements = tag.find_all("table")[:5]
    for tbl in table_elements:
        rows = []
        for tr in tbl.find_all("tr")[:100]:
            row = []
            for cell in tr.find_all(["th", "td"])[:20]:
                cell_text = cell.get_text(" ", strip=True)
                if cell_text:
                    row.append(cell_text)
            if row:
                rows.append(row)
        if rows:
            tables.append(rows)
    
    return SectionContent(
        headings=headings,
        text=text,
        links=links,
        images=images,
        lists=lists,
        tables=tables,
    )


def group_sections(url: str, html: str) -> Tuple[Meta, List[Section]]:
    """Group HTML into sections with improved logic"""
    # Use selectolax for faster parsing if available
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except:
        # Fallback to selectolax if BeautifulSoup fails
        try:
            parser = SelectolaxParser(html)
            # Convert to BeautifulSoup-like object
            soup = BeautifulSoup(parser.html, 'html.parser')
        except:
            return Meta(title="", description="", language="", canonical=None), []
    
    meta = extract_meta(soup, url)
    
    # Find candidate sections
    candidates = []
    
    # Priority 1: Semantic landmarks
    landmarks = soup.find_all(["header", "nav", "main", "section", "footer", "article", "aside"])
    candidates.extend(landmarks)
    
    # Priority 2: Divs with specific roles or classes
    div_candidates = soup.select('div[role="main"], div[role="article"], div.main, div.content, div.container')
    candidates.extend(div_candidates)
    
    # Priority 3: Body if no candidates found
    if not candidates:
        body = soup.find("body")
        if body:
            # Split body by major headings
            for h in body.find_all(["h1", "h2", "h3"]):
                section = soup.new_tag("div")
                current = h
                while current.next_sibling and current.next_sibling.name not in ["h1", "h2", "h3"]:
                    section.append(current.next_sibling)
                    current = current.next_sibling
                if section.contents:
                    candidates.append(section)
        
        if not candidates and body:
            candidates.append(body)
    
    sections: List[Section] = []
    seen_texts = set()  # Avoid duplicates
    
    for idx, tag in enumerate(candidates[:MAX_SECTIONS]):
        if is_noise_section(tag):
            continue
        
        content = extract_section_content(tag, base_url=url)
        
        # Skip empty sections
        if not content.text and not content.headings and not content.images:
            continue
        
        # Skip duplicate content
        text_hash = hashlib.md5(content.text[:500].encode()).hexdigest()
        if text_hash in seen_texts:
            continue
        seen_texts.add(text_hash)
        
        # Determine section type
        section_type = derive_section_type(tag, content)
        
        # Map to allowed types
        allowed_types = {"hero", "section", "nav", "footer", "list", "grid", "faq", "pricing", "table", "article", "form", "card", "sidebar"}
        if section_type not in allowed_types:
            section_type = "section"
        
        # Generate label
        label = derive_label(tag, section_type, content)
        
        # Get raw HTML
        raw_html = str(tag).strip()
        truncated = False
        if len(raw_html) > MAX_HTML_CHARS:
            raw_html = raw_html[:MAX_HTML_CHARS] + "..."
            truncated = True
        
        # Create section
        section = Section(
            id=f"{section_type}-{idx}",
            type=section_type,
            label=label,
            sourceUrl=url,
            content=content,
            rawHtml=raw_html,
            truncated=truncated,
        )
        sections.append(section)
    
    # If no sections found, create a fallback
    if not sections:
        body = soup.find("body") or soup
        content = extract_section_content(body, base_url=url)
        raw_html = str(body)[:MAX_HTML_CHARS]
        truncated = len(str(body)) > MAX_HTML_CHARS
        
        sections.append(
            Section(
                id="section-0",
                type="section",
                label="Full Page",
                sourceUrl=url,
                content=content,
                rawHtml=raw_html,
                truncated=truncated,
            )
        )
    
    return meta, sections


def needs_js_fallback(sections: List[Section], html: str, url: str) -> bool:
    """Smart JS fallback detection"""
    total_text = sum(len(s.content.text) for s in sections)
    
    indicators = {
        # Low content
        "low_text": total_text < 300,
        
        # JS warnings
        "js_warning": bool(re.search(r'enable\s+javascript|requires\s+javascript|please\s+enable\s+js', html, re.IGNORECASE)),
        "noscript": bool(re.search(r'<noscript>', html, re.IGNORECASE)),
        
        # SPA indicators
        "spa_markers": bool(re.search(r'<div\s+(id|class)=["\'](app|root|__next|react|vue|angular)["\']', html, re.IGNORECASE)),
        
        # Modern framework indicators
        "framework_indicators": bool(re.search(r'react|vue|angular|svelte|next\.js|nuxt\.js', html, re.IGNORECASE)),
        
        # Content loading patterns
        "loading_indicators": bool(re.search(r'loading|spinner|skeleton', html, re.IGNORECASE)),
        
        # Missing interactive elements
        "few_interactive": len(re.findall(r'<button|<a\s+href|<input', html)) < 3 and total_text > 0,
    }
    
    # Weighted scoring
    weights = {
        "low_text": 0.25,
        "js_warning": 0.20,
        "spa_markers": 0.20,
        "framework_indicators": 0.15,
        "loading_indicators": 0.10,
        "few_interactive": 0.10,
    }
    
    score = sum(weights.get(k, 0) for k, v in indicators.items() if v)
    return score >= 0.5  # Threshold for JS fallback


def perform_interactions(page, ctx: ScrapeContext):
    """Enhanced interaction strategy"""
    ctx.strategy = "js"
    
    try:
        # 1. Wait for initial load
        page.wait_for_load_state("networkidle", timeout=10000)
        
        # 2. Try to find and click tabs
        tab_selectors = [
            '[role="tab"]',
            '[role="tablist"] button',
            '[data-tab]',
            '.tab',
            '.tabs button',
            '.tab-button',
            '.tab-link',
            'button[aria-controls]',
            'button[aria-selected="false"]',
        ]
        
        tabs_clicked = 0
        for selector in tab_selectors:
            if tabs_clicked >= 3:
                break
            
            tabs = page.query_selector_all(selector)
            for tab in tabs[:3]:
                try:
                    # Check if tab is visible and clickable
                    if tab.is_visible():
                        text = (tab.inner_text() or "").strip()[:30]
                        before_content = page.content()
                        tab.click(timeout=3000)
                        page.wait_for_timeout(800)  # Wait for content change
                        
                        # Check if content actually changed
                        after_content = page.content()
                        if before_content != after_content:
                            ctx.clicks.append(f'tab:{selector}:"{text}"')
                            tabs_clicked += 1
                except:
                    continue
        
        # 3. Try load more buttons
        load_more_patterns = [
            "load more", "show more", "view more", "see more",
            "more results", "load additional", "expand", "next",
            "加载更多", "显示更多"  # Internationalization
        ]
        
        for pattern in load_more_patterns:
            try:
                buttons = page.query_selector_all(f'button:has-text("{pattern}"), a:has-text("{pattern}")')
                for btn in buttons[:2]:  # Try up to 2 buttons
                    if btn.is_visible():
                        btn.click(timeout=3000)
                        ctx.clicks.append(f'load_more:"{pattern}"')
                        page.wait_for_timeout(1200)
            except:
                continue
        
        # 4. Infinite scroll with content detection
        scroll_attempts = 0
        max_scrolls = 3
        
        while scroll_attempts < max_scrolls:
            # Get current scroll position and content
            scroll_height_before = page.evaluate("document.body.scrollHeight")
            content_before = page.content()
            
            # Scroll down
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)  # Wait for potential loading
            
            # Check if new content loaded
            scroll_height_after = page.evaluate("document.body.scrollHeight")
            content_after = page.content()
            
            if scroll_height_after > scroll_height_before and content_before != content_after:
                ctx.scrolls += 1
                scroll_attempts += 1
            else:
                # No new content, stop scrolling
                break
        
        # 5. Pagination
        next_attempts = 0
        max_next_pages = 2
        
        while next_attempts < max_next_pages:
            next_selectors = [
                'a[rel="next"]',
                'a:has-text("Next")',
                'a:has-text("»")',
                '.pagination-next',
                '.next-page',
                '[aria-label="Next"]',
                'button:has-text("Next")',
            ]
            
            clicked = False
            for selector in next_selectors:
                try:
                    next_element = page.query_selector(selector)
                    if next_element and next_element.is_visible():
                        next_element.click(timeout=5000)
                        page.wait_for_load_state("networkidle", timeout=10000)
                        
                        # Record the new page
                        if page.url not in ctx.pages:
                            ctx.pages.append(page.url)
                        
                        ctx.clicks.append(f'pagination:{selector}')
                        clicked = True
                        next_attempts += 1
                        break
                except:
                    continue
            
            if not clicked:
                break
        
        # 6. Take screenshot for debugging (optional)
        # screenshot = page.screenshot()
        # save_screenshot(screenshot)
        
    except Exception as e:
        ctx.errors.append(ErrorItem(message=str(e), phase="interactions"))


def scrape_with_playwright(url: str, ctx: ScrapeContext) -> Optional[str]:
    """Scrape using Playwright with enhanced features"""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Launch browser with options
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )
            
            # Create context with viewport
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Block unnecessary resources
            context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,eot,ttf,otf}", lambda route: route.abort())
            
            page = context.new_page()
            page.set_default_timeout(JS_TIMEOUT)
            
            # Add event listeners for debugging
            page.on("console", lambda msg: None)  # Log console messages
            page.on("pageerror", lambda err: ctx.errors.append(
                ErrorItem(message=f"Page error: {err}", phase="js")
            ))
            
            # Navigate to URL
            response = page.goto(url, wait_until="domcontentloaded", timeout=JS_TIMEOUT)
            
            if response and response.status >= 400:
                ctx.errors.append(ErrorItem(
                    message=f"HTTP {response.status}",
                    phase="navigation"
                ))
            
            # Record initial URL
            if page.url not in ctx.pages:
                ctx.pages.append(page.url)
            
            # Perform interactions
            perform_interactions(page, ctx)
            
            # Get final HTML
            html = page.content()
            
            # Close browser
            context.close()
            browser.close()
            
            return html
    
    except ImportError:
        ctx.errors.append(ErrorItem(
            message="Playwright not installed",
            phase="setup"
        ))
    except Exception as e:
        ctx.errors.append(ErrorItem(
            message=f"Playwright error: {str(e)}",
            phase="js"
        ))
    
    return None


def build_result(url: str) -> ScrapeResult:
    """Main function to build scrape result with enhanced features"""
    start_time = time.time()
    ctx = ScrapeContext(url=url)
    
    try:
        # Step 1: Static scraping
        static_html, response = fetch_static_html(url, ctx)
        
        if not static_html:
            raise Exception("Failed to fetch static HTML")
        
        # Check if response is HTML
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type:
            ctx.errors.append(ErrorItem(
                message=f"Content type is not HTML: {content_type}",
                phase="fetch"
            ))
        
        static_meta, static_sections = group_sections(url, static_html)
        static_meta.strategy = "static"
        
        chosen_meta = static_meta
        chosen_sections = static_sections
        
        # Step 2: Check if JS fallback is needed
        if needs_js_fallback(static_sections, static_html, url):
            js_html = scrape_with_playwright(url, ctx)
            
            if js_html and js_html != static_html:
                js_meta, js_sections = group_sections(url, js_html)
                js_meta.strategy = "js"
                
                # Compare results
                static_text = sum(len(s.content.text) for s in static_sections)
                js_text = sum(len(s.content.text) for s in js_sections)
                static_links = sum(len(s.content.links) for s in static_sections)
                js_links = sum(len(s.content.links) for s in js_sections)
                
                # Use JS results if they provide significantly more content
                if js_text > static_text * 1.5 or js_links > static_links * 2:
                    chosen_meta = js_meta
                    chosen_sections = js_sections
                else:
                    chosen_meta = static_meta
                    chosen_sections = static_sections
                    chosen_meta.strategy = "static+js"
            else:
                chosen_meta.strategy = "static"
                if js_html == static_html:
                    ctx.errors.append(ErrorItem(
                        message="JS rendering produced same content as static",
                        phase="js"
                    ))
        
        # Step 3: Post-process sections
        # Remove very similar sections
        unique_sections = []
        seen_hashes = set()
        
        for section in chosen_sections:
            # Create hash based on content
            content_str = f"{section.content.text[:200]}{''.join(section.content.headings)}"
            content_hash = hashlib.md5(content_str.encode()).hexdigest()
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_sections.append(section)
        
        chosen_sections = unique_sections
        
        # Step 4: Calculate statistics
        total_text = sum(len(s.content.text) for s in chosen_sections)
        total_links = sum(len(s.content.links) for s in chosen_sections)
        total_images = sum(len(s.content.images) for s in chosen_sections)
        
        # Add statistics to meta
        chosen_meta.title = chosen_meta.title or f"Scraped from {urlparse(url).netloc}"
        
        # Add performance info
        elapsed = time.time() - start_time
        ctx.errors.append(ErrorItem(
            message=f"Scraping completed in {elapsed:.2f}s. Found {len(chosen_sections)} sections with {total_text} chars, {total_links} links, {total_images} images.",
            phase="complete"
        ))
        
    except Exception as e:
        ctx.errors.append(ErrorItem(
            message=f"Unexpected error: {str(e)}",
            phase="unknown"
        ))
        
        # Create fallback result
        chosen_meta = Meta(
            title="Error",
            description="",
            language="",
            canonical=None,
            strategy="error",
        )
        chosen_sections = []
    
    # Build final result
    interactions = Interactions(
        clicks=ctx.clicks,
        scrolls=ctx.scrolls,
        pages=ctx.pages if ctx.pages else [url],
    )
    
    result = ScrapeResult(
        url=url,
        scrapedAt=datetime.now(timezone.utc),
        meta=chosen_meta,
        sections=chosen_sections,
        interactions=interactions,
        errors=ctx.errors,
    )
    
    return result