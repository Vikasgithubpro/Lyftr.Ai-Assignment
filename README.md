# 🚀 **Universal Website Scraper (MVP) + JSON Viewer**

*A full-stack solution built for the Lyftr AI Full-Stack Assignment*

This project implements a fully functional website scraping engine capable of handling both **static** and **JavaScript-rendered content**, performing **interactive actions** (tabs, load-more buttons), supporting **scroll/pagination depth ≥ 3**, and returning structured **section-aware JSON** exactly as required in the assignment.
A lightweight **JSON Viewer UI** is included for entering URLs, invoking the scraper, exploring output, and downloading results.

---

# ✨ **Key Features**

### 🔍 Intelligent Scraping Pipeline

* Static HTML scraping (httpx/requests + BeautifulSoup)
* Automated fallback to Playwright when static content is insufficient
* Heuristic-based detection of JS-rendered pages
* Full DOM extraction after JS execution

### 🧭 User Interaction Support

* Click flows (tabs, toggles, “Load more”/“Show more” buttons)
* Infinite scroll (multiple scroll depths)
* Pagination traversal (depth ≥ 3)
* All interactions recorded in output JSON

### 🧱 Structured JSON Output (Assignment Schema)

Includes:

* URL + scrapedAt timestamp
* meta fields (title, description, canonical, language)
* section-level breakdown:

  * headings
  * text
  * links (absolute URLs)
  * images
  * lists
  * tables
  * truncated raw HTML
* interactions: clicks, scrolls, pages visited
* errors with phase tracking

### 🖥️ Frontend Included

* URL input
* Loading indicator
* Section-by-section JSON viewer (expandable)
* “Download JSON” option

---

# 🧩 **Tech Stack**

(According to assignment requirements)


### Backend

* Python 3.10+
* FastAPI
* Playwright (Python)
* Uvicorn

### Frontend

* Jinja2 Templates

### Parsing & Utilities

* BeautifulSoup4
* httpx / requests

---

# 🏁 **How to Run the Project**

The evaluator will run your project using `run.sh`, but these are the exact manual commands used by the script.

### ▶ **Manual Startup**

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt

python -m playwright install

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

App will be live at:

👉 **[http://localhost:8000](http://localhost:8000)**

---

### ▶ Using `run.sh`



```bash
chmod +x run.sh
./run.sh
```

`run.sh` performs:

1. Virtual environment creation/activation
2. Dependency installation
3. Playwright browser installation
4. Starting FastAPI server at **port 8000**

---

# 🌐 **Endpoints**

| Endpoint   | Method | Description                                 |
| ---------- | ------ | ------------------------------------------- |
| `/`        | GET    | JSON Viewer UI                              |
| `/healthz` | GET    | Health check — must return `"status": "ok"` |
| `/scrape`  | POST   | Main scraping logic                         |

---

# 🧪 **Test URLs Used**

*(Assignment requires 3 URLs with descriptions)*


### 1️⃣ Static Website

**Wikipedia – Artificial Intelligence**
[https://en.wikipedia.org/wiki/Artificial_intelligence](https://en.wikipedia.org/wiki/Artificial_intelligence)
Used to verify section grouping, accurate metadata extraction, and clean HTML parsing.

### 2️⃣ JS-Rendered Site With Tabs

**Vercel Homepage**
[https://vercel.com/](https://vercel.com/)
Used to validate JS rendering fallback, tab-click interactions, and dynamic content extraction.

### 3️⃣ Pagination / Scroll Depth ≥ 3

**Hacker News**
[https://news.ycombinator.com/](https://news.ycombinator.com/)
Used to test multi-page traversal and scroll depth tracking.

---

# 📁 **Project Structure**

```
.
├── app/
│   ├── main.py
│   ├── scraper.py
│   ├── utils/
│   ├── templates/
│   └── static/
├── run.sh
├── requirements.txt
├── README.md
├── design_notes.md
└── capabilities.json
```
---

### 📸 Screenshots

#### Home Page – Hero Section
![Home](./screenshots/home-hero.png)

#### URL Input + Scraping Options
![URL Input](./screenshots/url-input-and-options.png)

#### Overview Metrics
![Overview](./screenshots/scrape-overview-metrics.png)

#### Page Metadata
![Metadata](./Project Snapshot/page-metadata.png)

#### Hero Section Viewer
![Hero Section](./Project Snapshot/section-viewer-hero.png)

#### Visualization Charts
![Charts](./Project Snapshot/visualization-charts.png)

#### Dashboard Main
![Dashboard Main](./Project Snapshot/dashboard-main.png)

#### System Status Dashboard
![Dashboard Status](./Project Snapshot/dashboard-system-status.png)

# 📝 **Known Limitations**

* JS-heavy frameworks with virtualized content may require additional wait strategies.
* Sites with strong bot detection may partially block scraping.
* Extremely large pages lead to raw HTML truncation for performance reasons.
* Certain interaction patterns may require custom selectors.

---

# ⚙️ **Evaluator Notes**

(Aligned with assignment evaluation stages)


* Fully compatible with `GET /healthz` and `POST /scrape` contract
* Returns all mandatory JSON fields
* Supports interaction-based content expansion
* UI allows section inspection + JSON download
* Error-handling logic ensures partial results aren’t lost

---

# 👤 **Author**

**Vikas Singh**
*Full-Stack Developer*

---

# ✔️ **This Repository Contains All Mandatory Assignment Files**

* `run.sh`
* `README.md`
* `design_notes.md`
* `capabilities.json`

All deliverables follow the assignment requirements precisely and are structured for easy evaluation.

---
