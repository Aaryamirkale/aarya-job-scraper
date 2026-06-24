# 🎯 Aarya's Job Board — Auto Job Scraper

Scrapes **9 platforms** for Data Science, ML, Analytics, and AI roles every 3 hours.
Filters for H1B-friendly roles. Zero cost. No email needed.

## Platforms Scraped
| Platform | Type | Notes |
|---|---|---|
| Indeed | RSS | H1B keyword filtered |
| LinkedIn | Public search | Last 3 hours of postings |
| RemoteOK | Public API | Remote DS/ML roles |
| Wellfound (AngelList) | Public search | Startup jobs, OPT-friendly |
| Glassdoor | Public search | Company reviews included |
| HN Who's Hiring | Algolia API | Monthly thread, visa-friendly startups |
| Greenhouse (Direct) | ATS API | 19 verified H1B sponsors |
| Lever (Direct) | ATS API | 7 healthcare/AI companies |
| Simplify.jobs | Public search | Pre-filtered H1B sponsors |

## Roles Tracked
- Data Scientist, Applied Scientist, Research Scientist, Quantitative Analyst
- Machine Learning Engineer, ML Engineer, MLOps Engineer
- AI Engineer, Applied AI, Applied ML
- Forward Deployed Engineer, Forward Deployed AI Engineer
- Data Analyst, Clinical Data Analyst, Healthcare Data Scientist, Product Analyst
- Business Intelligence Analyst, BI Analyst, BI Developer
- Analytics Engineer, Data Engineer

## Setup (5 minutes)

### 1. Create GitHub repo
Go to github.com → New repository → Name: `aarya-job-scraper` → **Public** → Create

### 2. Upload these files
Drag and drop all files into the repo, or use:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/aaryamirkale/aarya-job-scraper.git
git push -u origin main
```

### 3. Enable GitHub Pages
Settings → Pages → Source: `main` branch → `/results` folder → Save

### 4. Run it manually first
Actions tab → "Job Scraper - Every 3 Hours" → Run workflow → Wait ~2 minutes

### 5. View your job board
`https://aaryamirkale.github.io/aarya-job-scraper/jobs.html`

That's it! It runs every 3 hours forever for free.

## Features
- 🟢 Green badge = H1B sponsorship signal detected in listing
- 🟡 Yellow badge = Verify sponsorship directly
- 🔍 Search bar — filter by title, company, location, source
- Never shows same job twice (tracks seen jobs)
- Mobile responsive
- Source breakdown stats at top
