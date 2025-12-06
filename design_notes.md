# Design Notes

## Static vs JS Fallback

- Strategy:
  - Always attempt a static scrape first using HTTPX + BeautifulSoup4.
  - Compute:
    - `total_text = sum(len(section.content.text) for section in sections)`
  - If `total_text < 500` characters or the HTML contains phrases like “enable JavaScript”, then trigger a JS-rendered fallback via Playwright.
  - After JS scraping, parse sections again from the JS-rendered HTML and compare total text length with the static result:
    - If JS result has >= text, prefer JS sections/meta.
    - Otherwise keep static sections/meta and mark strategy as `"static+js"`.

## Wait Strategy for JS

- [x] Network idle
- [x] Fixed sleep
- [x] Wait for selectors (indirectly via `query_selector_all`)
- Details:
  - Initial navigation uses `page.goto(url, wait_until="networkidle", timeout=JS_TIMEOUT)` to wait until the network quiets.
  - After each click (tabs, “load more”), the page waits a short fixed time (~800–1200 ms) to allow content to update.
  - Infinite scroll uses `page.mouse.wheel(0, 2000)` followed by a 1500 ms sleep per scroll.

## Click & Scroll Strategy

- Click flows implemented:
  - Tabs:
    - Try a small set of tab-like selectors:
      - `[role="tab"]`, `[data-tab]`, `.tab`, `.tabs button`.
    - Click up to the first 3 matching elements, record a click description (selector + short text).
  - “Load more / Show more / Next”:
    - Scan up to 20 `button`/`a` elements.
    - If inner text contains “load more”, “show more”, “more results”, or “next” (case-insensitive), attempt a click and wait ~1200 ms.

- Scroll / pagination approach:
  - Infinite scroll:
    - Perform at least 3 scroll operations with `page.mouse.wheel(0, 2000)`.
  - Pagination:
    - Try to follow pagination links by:
      - `a[rel=next]` or `a:has-text("Next")`.
    - At most 2 additional pages are loaded this way.
  - Each distinct `page.url` after navigation is added to `interactions.pages`.

- Stop conditions (max depth / timeout):
  - Max 3 scroll operations (depth ≥ 3).
  - Max 2 “next” page navigations.
  - Per navigation and major interaction, a timeout (`JS_TIMEOUT`) is applied, and on error the operation is skipped and recorded.

## Section Grouping & Labels

- How DOM is grouped into sections:
  - Prefer semantic landmarks:
    - Collect all `<header>`, `<nav>`, `<main>`, `<section>`, and `<footer>` tags.
  - If no such landmarks are found, fall back to `<body>`.
  - For each candidate:
    - Skip sections identified as “noise” (cookie banners, modals, etc.) based on ID/class keywords.
    - Extract headings, main text, links, images, lists, and tables.

- How `type` and `label` are derived:
  - `type`:
    - `"hero"`: `<header>` or elements whose class/id contains “hero”.
    - `"nav"`: `<nav>`.
    - `"footer"`: `<footer>`.
    - `"pricing"`: class/id contains “pricing”.
    - `"faq"`: class/id contains “faq”.
    - `"grid"`: class contains “grid”.
    - `"list"`: any section containing at least one `<ul>`/`<ol>`.
    - Otherwise `"section"`, and mapped to `"unknown"` if it’s not one of the allowed types from the spec.
  - `label`:
    - If any `h1–h3` heading exists, use the first heading (trimmed).
    - For specific section types:
      - `"hero"` → `"Hero"`, `"nav"` → `"Navigation"`, `"footer"` → `"Footer"`, etc.
    - Otherwise, derive from the first 5–7 words of the section text.
    - If there is no text, fall back to the capitalized type (`"Section"`, `"Unknown"`, etc.).

## Noise Filtering & Truncation

- What is filtered out:
  - Sections where ID/class contains common overlay / cookie / modal keywords:
    - `"cookie"`, `"consent"`, `"banner"`, `"modal"`, `"popup"`, `"newsletter"`, `"subscribe"`.
  - Within each section, `<script>`, `<style>`, and `<noscript>` tags are removed before text extraction.

- How `rawHtml` is truncated and `truncated` is set:
  - `rawHtml` is produced by `str(tag)` for each section.
  - If the length of this string exceeds `MAX_HTML_CHARS` (currently 4000 characters), it is sliced to that length and `truncated` is set to `true`.
  - Otherwise, `truncated` is `false`.
