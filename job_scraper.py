"""
Aarya's Job Scraper — GitHub Actions Version
Runs every 3 hours, saves results to results/jobs.html
Platforms: Indeed, RemoteOK, HN Who's Hiring, LinkedIn RSS,
           Greenhouse, Lever, Wellfound, Simplify, Glassdoor
"""

import feedparser
import requests
from bs4 import BeautifulSoup
import json
import os
import hashlib
from datetime import datetime, timezone, timedelta

# Jobs older than this will be filtered out
MAX_AGE_HOURS = 24

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SEEN_JOBS_FILE = "results/seen_jobs.json"
OUTPUT_HTML = "results/jobs.html"
OUTPUT_JSON = "results/jobs.json"
MAX_JOBS_TO_SHOW = 300

TARGET_TITLES = [
    # Data Science
    "data scientist",
    "data science",
    "applied scientist",
    "quantitative analyst",
    "research scientist",
    # ML / AI
    "machine learning engineer",
    "ml engineer",
    "ai engineer",
    "mlops engineer",
    "applied ml",
    "applied ai",
    "forward deployed engineer",
    "forward deployed ai",
    # Analytics
    "data analyst",
    "business intelligence analyst",
    "bi analyst",
    "bi developer",
    "analytics engineer",
    "product analyst",
    "clinical data analyst",
    "healthcare data scientist",
    "health data analyst",
    # Data Engineering
    "data engineer",
    "analytics data engineer",
]

H1B_POSITIVE_KEYWORDS = [
    "h1b", "h-1b", "visa sponsor", "sponsorship available",
    "will sponsor", "sponsoring visa", "opt eligible", "stem opt",
    "immigration support", "work authorization provided",
    "visa support", "relocation assistance"
]

DISQUALIFY_KEYWORDS = [
    "clearance required", "secret clearance", "top secret", "ts/sci",
    "us citizen only", "citizens only", "no sponsorship",
    "cannot sponsor", "will not sponsor", "sponsorship not available",
    "not able to sponsor", "itar", "security clearance required",
    "must be authorized to work", "no visa", "citizen or permanent resident only",
    "must be a us citizen", "requires us citizenship"
]

TARGET_LOCATIONS = [
    "new york", "boston", "chicago", "austin", "remote", "hybrid",
    "san francisco", "seattle", "philadelphia", "new jersey",
    "connecticut", "cambridge", "houston", "dallas", "atlanta",
    "united states", "nationwide", "anywhere", "los angeles",
    "washington dc", "baltimore", "raleigh", "nashville", "miami",
    "denver", "portland", "minneapolis", "charlotte", "pittsburgh",
    "san diego", "phoenix", "salt lake", "columbus", "cleveland"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return []

def save_seen_jobs(seen):
    os.makedirs("results", exist_ok=True)
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen[-5000:], f)

def job_id(title, company):
    raw = f"{title.lower().strip()[:50]}{company.lower().strip()[:30]}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_relevant_title(title):
    t = title.lower()
    return any(kw in t for kw in TARGET_TITLES)

def is_disqualified(text):
    t = text.lower()
    return any(kw in t for kw in DISQUALIFY_KEYWORDS)

def has_h1b_signal(text):
    t = text.lower()
    return any(kw in t for kw in H1B_POSITIVE_KEYWORDS)

def is_target_location(text):
    if not TARGET_LOCATIONS:
        return True
    t = text.lower()
    return any(loc in t for loc in TARGET_LOCATIONS)

def clean_text(html_text):
    return BeautifulSoup(str(html_text), "html.parser").get_text(separator=" ").strip()

def is_within_24hrs(published_parsed=None, published_str=None):
    """Returns True if job was posted within last 24 hours"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_HOURS)
    try:
        if published_parsed:
            dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
            return dt >= cutoff
        if published_str:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(published_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt >= cutoff
    except Exception:
        pass
    return True  # If date unparseable, include it

def make_job(title, company, link, location, source, full_text, summary=""):
    return {
        "title": title[:80],
        "company": company[:60],
        "link": link,
        "location": location[:60] if location else "USA",
        "source": source,
        "h1b_signal": has_h1b_signal(full_text),
        "summary": summary[:200].strip(),
        "found_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

# ─── SCRAPERS ─────────────────────────────────────────────────────────────────

def scrape_indeed_rss():
    jobs = []
    queries = [
        "data+scientist+h1b+sponsor",
        "machine+learning+engineer+visa+sponsorship",
        "data+analyst+h1b",
        "ml+engineer+visa+sponsor",
        "ai+engineer+h1b",
        "data+engineer+visa+sponsor",
        "business+intelligence+analyst+sponsorship",
        "mlops+engineer+h1b",
        "clinical+data+analyst",
        "healthcare+data+scientist",
        "product+analyst+h1b",
        "forward+deployed+engineer",
        "research+scientist+data",
        "analytics+engineer+h1b",
    ]
    for query in queries:
        try:
            url = f"https://www.indeed.com/rss?q={query}&l=United+States&sort=date&fromage=1"
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                raw_title = entry.get("title", "")
                title = raw_title.split(" - ")[0].strip()
                summary_html = entry.get("summary", "")
                summary = clean_text(summary_html)
                location = entry.get("location", "")
                link = entry.get("link", "")
                company = raw_title.split(" - ")[-1].strip() if " - " in raw_title else "See listing"
                full_text = f"{title} {summary} {location} {company}"

                if not is_relevant_title(title):
                    continue
                if is_disqualified(full_text):
                    continue
                if not is_target_location(f"{location} {summary}"):
                    continue
                if not is_within_24hrs(
                    published_parsed=entry.get("published_parsed"),
                    published_str=entry.get("published")
                ):
                    continue

                jobs.append(make_job(title, company, link, location, "Indeed", full_text, summary[:200]))
        except Exception as e:
            print(f"Indeed error ({query}): {e}")
    return jobs


def scrape_linkedin_rss():
    """LinkedIn public job RSS feeds"""
    jobs = []
    searches = [
        "data+scientist",
        "machine+learning+engineer",
        "data+analyst",
        "AI+engineer",
        "data+engineer",
        "business+intelligence+analyst",
        "mlops+engineer",
        "analytics+engineer",
        "clinical+data+analyst",
        "healthcare+data+scientist",
        "product+analyst",
        "research+scientist",
    ]
    for kw in searches:
        try:
            url = f"https://www.linkedin.com/jobs/search/?keywords={kw}&location=United+States&f_TPR=r86400&sortBy=DD"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="base-card")[:12]
            for card in cards:
                try:
                    title_el = card.find("h3", class_="base-search-card__title")
                    company_el = card.find("h4", class_="base-search-card__subtitle")
                    location_el = card.find("span", class_="job-search-card__location")
                    link_el = card.find("a", class_="base-card__full-link")
                    title = title_el.get_text(strip=True) if title_el else ""
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    location = location_el.get_text(strip=True) if location_el else ""
                    link = link_el.get("href", "") if link_el else ""
                    full_text = f"{title} {company} {location}"

                    if not is_relevant_title(title):
                        continue
                    if is_disqualified(full_text):
                        continue

                    jobs.append(make_job(title, company, link, location, "LinkedIn", full_text))
                except Exception:
                    continue
        except Exception as e:
            print(f"LinkedIn error ({kw}): {e}")
    return jobs


def scrape_remoteok():
    jobs = []
    tags = ["data-science", "machine-learning", "data-analyst", "ai", "data-engineer"]
    for tag in tags:
        try:
            url = f"https://remoteok.com/api?tag={tag}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for item in data[1:25]:
                if not isinstance(item, dict):
                    continue
                title = item.get("position", "")
                company = item.get("company", "Unknown")
                location = item.get("location", "Remote")
                link = item.get("url", f"https://remoteok.com/remote-jobs/{item.get('id','')}")
                description = clean_text(item.get("description", ""))
                tags_text = " ".join(item.get("tags", []))
                full_text = f"{title} {company} {description} {tags_text}"

                if not is_relevant_title(title):
                    continue
                if is_disqualified(full_text):
                    continue
                # RemoteOK epoch timestamp filter (24hrs)
                epoch = item.get("epoch", 0)
                if epoch:
                    from datetime import timezone, timedelta
                    cutoff_epoch = (datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)).timestamp()
                    if epoch < cutoff_epoch:
                        continue

                jobs.append(make_job(title, company, link, location, "RemoteOK", full_text, description[:200]))
        except Exception as e:
            print(f"RemoteOK error ({tag}): {e}")
    return jobs


def scrape_wellfound():
    """Wellfound (AngelList) — startup jobs, often OPT friendly"""
    jobs = []
    searches = [
        "data-scientist", "machine-learning-engineer",
        "data-analyst", "ai-engineer", "data-engineer"
    ]
    for role in searches:
        try:
            url = f"https://wellfound.com/role/r/{role}"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", attrs={"data-test": "StartupResult"})[:10]
            for card in cards:
                try:
                    title_el = card.find("a", attrs={"data-test": "job-link"})
                    company_el = card.find("a", attrs={"data-test": "startup-link"})
                    location_el = card.find("span", attrs={"data-test": "location"})
                    title = title_el.get_text(strip=True) if title_el else role.replace("-", " ").title()
                    company = company_el.get_text(strip=True) if company_el else "Startup"
                    location = location_el.get_text(strip=True) if location_el else "Remote"
                    link = "https://wellfound.com" + title_el.get("href", "") if title_el else url
                    full_text = f"{title} {company} {location}"

                    if is_disqualified(full_text):
                        continue

                    jobs.append(make_job(title, company, link, location, "Wellfound", full_text))
                except Exception:
                    continue
        except Exception as e:
            print(f"Wellfound error ({role}): {e}")
    return jobs


def scrape_glassdoor_rss():
    """Glassdoor job RSS feeds"""
    jobs = []
    queries = [
        "data-scientist", "machine-learning-engineer",
        "data-analyst", "ai-engineer", "data-engineer",
        "business-intelligence-analyst"
    ]
    for query in queries:
        try:
            url = f"https://www.glassdoor.com/Job/jobs.htm?suggestCount=0&suggestChosen=false&clickSource=searchBtn&typedKeyword={query}&sc.keyword={query}&locT=N&locId=1&jobType=&context=Jobs&action=search&countryRedirect=true"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("li", class_="react-job-listing")[:10]
            for card in cards:
                try:
                    title_el = card.find("a", class_="jobLink")
                    company_el = card.find("div", class_="d-flex justify-content-between align-items-start")
                    location_el = card.find("span", class_="loc")
                    title = title_el.get_text(strip=True) if title_el else ""
                    company = company_el.get_text(strip=True)[:40] if company_el else "Unknown"
                    location = location_el.get_text(strip=True) if location_el else ""
                    link = "https://www.glassdoor.com" + title_el.get("href", "") if title_el else ""
                    full_text = f"{title} {company} {location}"

                    if not is_relevant_title(title):
                        continue
                    if is_disqualified(full_text):
                        continue

                    jobs.append(make_job(title, company, link, location, "Glassdoor", full_text))
                except Exception:
                    continue
        except Exception as e:
            print(f"Glassdoor error ({query}): {e}")
    return jobs


def scrape_hn_whoishiring():
    jobs = []
    try:
        search_url = "https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+hiring&tags=story&hitsPerPage=1"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200:
            return jobs
        thread_id = resp.json()["hits"][0]["objectID"]
        comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&hitsPerPage=150"
        resp2 = requests.get(comments_url, timeout=10)
        if resp2.status_code != 200:
            return jobs
        for hit in resp2.json().get("hits", []):
            text = hit.get("comment_text", "")
            if not text:
                continue
            clean = clean_text(text)
            if not is_relevant_title(clean[:300]):
                continue
            if is_disqualified(clean):
                continue
            lines = clean.split("\n")
            first_line = lines[0][:120]
            parts = first_line.split("|")
            company = parts[0].strip()[:60] if parts else "HN Company"
            title = parts[1].strip()[:80] if len(parts) > 1 else "Data/ML Role"
            location = parts[2].strip()[:60] if len(parts) > 2 else "See listing"
            link = f"https://news.ycombinator.com/item?id={hit.get('objectID','')}"
            full_text = clean
            jobs.append(make_job(title, company, link, location, "HN Who's Hiring", full_text, clean[:200]))
    except Exception as e:
        print(f"HN error: {e}")
    return jobs


def scrape_greenhouse_boards():
    """Direct from verified H1B sponsor Greenhouse boards"""
    jobs = []
    companies = [
        # Healthcare (cap-exempt)
        ("NYU Langone Health", "nyulangone"),
        ("Boston Children's Hospital", "bostonchildrenshospital"),
        ("Beth Israel Deaconess", "bidmc"),
        ("Columbia University", "columbiauniversity"),
        # Tech / Finance
        ("Flatiron Health", "flatironhealth"),
        ("Palantir Technologies", "palantir"),
        ("Western Alliance Bank", "westernalliancebank"),
        ("GumGum", "gumgum"),
        ("FanDuel", "fanduel"),
        ("Upgrade", "upgrade"),
        ("Bandwidth", "bandwidth"),
        # Consulting
        ("Capgemini", "capgemini"),
        ("Infosys", "infosys"),
        # Life Sciences
        ("Thermo Fisher Scientific", "thermofisher"),
        ("AbbVie", "abbvie"),
        ("Amgen", "amgen"),
        # Other verified
        ("Charles Schwab", "schwab"),
        ("Optum", "optum"),
        ("CVS Health", "cvshealth"),
    ]
    for company_name, board_token in companies:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for job in data.get("jobs", [])[:20]:
                title = job.get("title", "")
                link = job.get("absolute_url", "")
                location_data = job.get("location", {})
                location = location_data.get("name", "See listing") if location_data else "See listing"
                content = clean_text(job.get("content", ""))
                full_text = f"{title} {content} {location}"

                if not is_relevant_title(title):
                    continue
                if is_disqualified(full_text):
                    continue

                jobs.append({
                    "title": title[:80],
                    "company": company_name,
                    "link": link,
                    "location": location[:60],
                    "source": f"Direct ({company_name})",
                    "h1b_signal": True,  # Verified sponsors
                    "summary": content[:200].strip(),
                    "found_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                })
        except Exception as e:
            print(f"Greenhouse error ({company_name}): {e}")
    return jobs


def scrape_lever_boards():
    """Lever ATS — used by many startups and mid-size companies"""
    jobs = []
    companies = [
        ("Waymo", "waymo"),
        ("Scale AI", "scaleai"),
        ("Recursion Pharmaceuticals", "recursionpharma"),
        ("Tempus", "tempus"),
        ("Color Health", "color"),
        ("Notable Health", "notablehealth"),
        ("Innovaccer", "innovaccer"),
    ]
    for company_name, lever_slug in companies:
        try:
            url = f"https://api.lever.co/v0/postings/{lever_slug}?mode=json"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            for job in resp.json()[:20]:
                title = job.get("text", "")
                link = job.get("hostedUrl", "")
                location = job.get("categories", {}).get("location", "See listing")
                description = clean_text(job.get("description", ""))
                full_text = f"{title} {description} {location}"

                if not is_relevant_title(title):
                    continue
                if is_disqualified(full_text):
                    continue
                # Lever createdAt timestamp filter (24hrs)
                created_at = job.get("createdAt", 0)
                if created_at:
                    from datetime import timezone, timedelta
                    cutoff_ms = (datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)).timestamp() * 1000
                    if created_at < cutoff_ms:
                        continue

                jobs.append(make_job(title, company_name, link, location,
                                     f"Lever ({company_name})", full_text, description[:200]))
        except Exception as e:
            print(f"Lever error ({company_name}): {e}")
    return jobs


def scrape_simplify():
    """Simplify.jobs — already filters H1B sponsors"""
    jobs = []
    try:
        url = "https://simplify.jobs/jobs?categories=Data+Science&categories=Machine+Learning&categories=Data+Engineering&h1bSponsored=true"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return jobs
        soup = BeautifulSoup(resp.text, "html.parser")
        # Try multiple card selectors since Simplify updates their UI
        cards = (soup.find_all("div", attrs={"data-cy": "job-card"}) or
                 soup.find_all("div", class_="job-card") or
                 soup.find_all("article"))[:20]
        for card in cards:
            try:
                title_el = card.find(["h2", "h3"])
                link_el = card.find("a")
                title = title_el.get_text(strip=True) if title_el else ""
                link = "https://simplify.jobs" + link_el.get("href", "") if link_el else ""
                full_text = card.get_text()
                company = "See listing"
                location = "USA"

                if not is_relevant_title(title):
                    continue

                jobs.append({
                    "title": title[:80],
                    "company": company,
                    "link": link,
                    "location": location,
                    "source": "Simplify (H1B Verified)",
                    "h1b_signal": True,
                    "summary": "H1B sponsored role — verified by Simplify",
                    "found_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                })
            except Exception:
                continue
    except Exception as e:
        print(f"Simplify error: {e}")
    return jobs




def scrape_google_careers():
    """Google Careers API — data science and analytics roles"""
    jobs = []
    queries = [
        "data scientist", "machine learning engineer",
        "data analyst", "ai engineer", "data engineer",
        "research scientist", "applied scientist", "analytics engineer"
    ]
    try:
        for query in queries:
            url = f"https://careers.google.com/api/jobs/results/?q={query.replace(' ', '+')}&location=United+States&distance=50&page_size=20&sort_by=date"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for job in data.get("jobs", [])[:10]:
                title = job.get("title", "")
                link = "https://careers.google.com/jobs/results/" + str(job.get("job_id", ""))
                locations = job.get("locations", [{}])
                location = locations[0].get("display", "USA") if locations else "USA"
                description = clean_text(job.get("description", ""))
                full_text = f"{title} {description} {location} Google"

                if not is_relevant_title(title):
                    continue
                if is_disqualified(full_text):
                    continue

                # Google posts dates in apply_url or description — include all as Google is cap-subject sponsor
                jobs.append({
                    "title": title[:80],
                    "company": "Google",
                    "link": link,
                    "location": location[:60],
                    "source": "Google Careers",
                    "h1b_signal": True,  # Google is a top H1B sponsor
                    "summary": description[:200].strip(),
                    "found_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                })
    except Exception as e:
        print(f"Google Careers error: {e}")
    return jobs


def scrape_meta_careers():
    """Meta Careers API — data science and analytics roles"""
    jobs = []
    queries = [
        "data scientist", "machine learning engineer",
        "data analyst", "ai engineer", "research scientist"
    ]
    try:
        for query in queries:
            url = f"https://www.metacareers.com/graphql"
            payload = {
                "operationName": "SearchJobsQuery",
                "variables": {
                    "search_input": {
                        "q": query,
                        "divisions": [],
                        "offices": [],
                        "roles": [],
                        "leadership_levels": [],
                        "saved_jobs": [],
                        "saved_searches": [],
                        "sub_teams": [],
                        "teams": [],
                        "is_leadership": False,
                        "is_remote_only": False,
                        "sort_by_new": True,
                    }
                },
                "query": "query SearchJobsQuery($search_input: JobSearchInput!) { job_search: job_search(input: $search_input) { jobs { id title location { city state country } post_date } } }"
            }
            resp = requests.post(url, json=payload, headers={**HEADERS, "Content-Type": "application/json"}, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            job_list = data.get("data", {}).get("job_search", {}).get("jobs", [])
            for job in job_list[:10]:
                title = job.get("title", "")
                job_id = job.get("id", "")
                link = f"https://www.metacareers.com/jobs/{job_id}/"
                loc = job.get("location", {})
                location = f"{loc.get('city','')}, {loc.get('state','')}" if loc else "USA"
                full_text = f"{title} {location} Meta"

                if not is_relevant_title(title):
                    continue
                if is_disqualified(full_text):
                    continue

                # Date filter
                post_date = job.get("post_date", "")
                if post_date:
                    try:
                        from datetime import timezone, timedelta
                        dt = datetime.fromisoformat(post_date.replace("Z", "+00:00"))
                        if dt < datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS):
                            continue
                    except Exception:
                        pass

                jobs.append({
                    "title": title[:80],
                    "company": "Meta",
                    "link": link,
                    "location": location[:60],
                    "source": "Meta Careers",
                    "h1b_signal": True,  # Meta is a top H1B sponsor
                    "summary": f"Data/ML role at Meta — {location}",
                    "found_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                })
    except Exception as e:
        print(f"Meta Careers error: {e}")
    return jobs


def scrape_amazon_careers():
    """Amazon Jobs API — data science and analytics roles"""
    jobs = []
    queries = [
        "data scientist", "machine learning engineer",
        "data analyst", "applied scientist", "data engineer"
    ]
    try:
        for query in queries:
            url = f"https://www.amazon.jobs/en/search.json?base_query={query.replace(' ', '+')}&loc_query=United+States&job_count=10&result_limit=10&sort=recent&category%5B%5D=data-science&category%5B%5D=machine-learning-science"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for job in data.get("jobs", [])[:10]:
                title = job.get("title", "")
                job_path = job.get("job_path", "")
                link = f"https://www.amazon.jobs{job_path}"
                location = job.get("location", "USA")
                description = clean_text(job.get("description", ""))
                full_text = f"{title} {description} {location} Amazon"
                posted_date = job.get("posted_date", "")

                if not is_relevant_title(title):
                    continue
                if is_disqualified(full_text):
                    continue

                # Date filter — Amazon uses "June 24, 2026" format
                if posted_date:
                    try:
                        from datetime import timezone, timedelta
                        dt = datetime.strptime(posted_date, "%B %d, %Y").replace(tzinfo=timezone.utc)
                        if dt < datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS):
                            continue
                    except Exception:
                        pass

                jobs.append({
                    "title": title[:80],
                    "company": "Amazon",
                    "link": link,
                    "location": location[:60],
                    "source": "Amazon Careers",
                    "h1b_signal": True,  # Amazon is top H1B sponsor
                    "summary": description[:200].strip(),
                    "found_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                })
    except Exception as e:
        print(f"Amazon Careers error: {e}")
    return jobs

# ─── HTML GENERATOR ───────────────────────────────────────────────────────────

def load_all_jobs():
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, "r") as f:
            return json.load(f)
    return []

def save_all_jobs(jobs):
    os.makedirs("results", exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(jobs[:MAX_JOBS_TO_SHOW], f, indent=2)

def generate_html(all_jobs):
    h1b_jobs = [j for j in all_jobs if j.get("h1b_signal")]
    other_jobs = [j for j in all_jobs if not j.get("h1b_signal")]

    source_colors = {
        "Indeed": "#2563eb",
        "LinkedIn": "#0a66c2",
        "RemoteOK": "#7c3aed",
        "HN Who's Hiring": "#ea580c",
        "Wellfound": "#16a34a",
        "Glassdoor": "#059669",
        "Simplify (H1B Verified)": "#dc2626",
    }

    def job_row(job):
        badge_color = "#16a34a" if job.get("h1b_signal") else "#d97706"
        badge_bg = "#dcfce7" if job.get("h1b_signal") else "#fef3c7"
        badge_text = "✓ H1B" if job.get("h1b_signal") else "? Verify"
        source = job.get("source", "")
        sc = "#6b7280"
        for k, v in source_colors.items():
            if k in source:
                sc = v
                break
        if "Direct" in source or "Lever" in source:
            sc = "#16a34a"

        return f"""
        <tr class="job-row" style="border-bottom:1px solid #f3f4f6;">
            <td style="padding:12px 8px;">
                <a href="{job['link']}" target="_blank"
                   style="font-weight:600;color:#1d4ed8;text-decoration:none;font-size:13px;">
                   {job['title']}</a>
                <div style="font-size:11px;color:#9ca3af;margin-top:2px;">{job.get('summary','')[:100]}{'...' if len(job.get('summary',''))>100 else ''}</div>
            </td>
            <td style="padding:12px 8px;font-size:13px;color:#374151;">{job['company']}</td>
            <td style="padding:12px 8px;font-size:12px;color:#6b7280;">{job['location']}</td>
            <td style="padding:12px 8px;">
                <span style="background:{badge_bg};color:{badge_color};padding:3px 8px;
                             border-radius:20px;font-size:11px;font-weight:700;">{badge_text}</span>
            </td>
            <td style="padding:12px 8px;font-size:11px;color:{sc};">{source}</td>
            <td style="padding:12px 8px;font-size:11px;color:#9ca3af;white-space:nowrap;">{job.get('found_at','')[:10]}</td>
            <td style="padding:12px 8px;">
                <a href="{job['link']}" target="_blank"
                   style="background:#1d4ed8;color:white;padding:5px 10px;border-radius:6px;
                          text-decoration:none;font-size:11px;white-space:nowrap;">Apply →</a>
            </td>
        </tr>"""

    def table(title, jobs, color):
        if not jobs:
            return ""
        rows = "".join(job_row(j) for j in jobs)
        return f"""
        <h2 style="color:{color};margin:28px 0 10px;font-size:17px;">{title} ({len(jobs)})</h2>
        <div style="overflow-x:auto;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <table style="width:100%;border-collapse:collapse;background:white;">
            <thead><tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb;">
                <th style="padding:9px 8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">Role</th>
                <th style="padding:9px 8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">Company</th>
                <th style="padding:9px 8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">Location</th>
                <th style="padding:9px 8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">H1B</th>
                <th style="padding:9px 8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">Source</th>
                <th style="padding:9px 8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;">Found</th>
                <th style="padding:9px 8px;"></th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table></div>"""

    # Source breakdown stats
    from collections import Counter
    source_counts = Counter(j.get("source","").split("(")[0].strip() for j in all_jobs)
    source_pills = "".join(
        f'<span style="background:#f3f4f6;color:#374151;padding:3px 10px;border-radius:20px;font-size:12px;margin:2px;">{s}: {c}</span>'
        for s, c in source_counts.most_common()
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>Aarya's Job Board — {datetime.utcnow().strftime('%b %d %Y')}</title>
    <style>
        * {{ box-sizing:border-box; }}
        body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                background:#f3f4f6;margin:0;padding:16px; }}
        input {{ width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;
                font-size:14px;margin-bottom:12px;outline:none; }}
        input:focus {{ border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,0.15); }}
        .job-row:hover {{ background:#f8faff; }}
        @media(max-width:600px) {{ td:nth-child(4),td:nth-child(5),th:nth-child(4),th:nth-child(5) {{ display:none; }} }}
    </style>
</head>
<body>
<div style="max-width:1200px;margin:0 auto;">

    <div style="background:linear-gradient(135deg,#1e3a5f,#1d4ed8);color:white;
                padding:22px 24px;border-radius:12px;margin-bottom:20px;">
        <h1 style="margin:0;font-size:22px;">🎯 Aarya's Job Board</h1>
        <p style="margin:6px 0 0;opacity:0.85;font-size:14px;">
            {len(all_jobs)} roles tracked &bull; {len(h1b_jobs)} H1B signal &bull;
            Updated: {datetime.utcnow().strftime('%b %d, %Y %H:%M UTC')} &bull;
            Runs every 3 hours via GitHub Actions
        </p>
    </div>

    <div style="background:white;padding:16px;border-radius:8px;margin-bottom:16px;
                box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <input type="text" id="search" placeholder="🔍 Search by title, company, location, or source..."
               oninput="filterJobs()">
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;">
            <span style="background:#dcfce7;color:#16a34a;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;">
                🟢 {len(h1b_jobs)} H1B Signal
            </span>
            <span style="background:#fef3c7;color:#d97706;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;">
                🟡 {len(other_jobs)} Verify Sponsorship
            </span>
            <span style="background:#eff6ff;color:#2563eb;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;">
                📋 {len(all_jobs)} Total
            </span>
        </div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;">{source_pills}</div>
    </div>

    <div id="job-content">
        {table("🟢 H1B Sponsor Signal", h1b_jobs, "#16a34a")}
        {table("🟡 Verify Sponsorship Directly", other_jobs, "#d97706")}
    </div>

    <p style="text-align:center;color:#9ca3af;font-size:12px;margin-top:24px;">
        Auto-updated every 3 hours. Always verify H1B sponsorship directly with the employer before applying.
    </p>
</div>

<script>
function filterJobs() {{
    const q = document.getElementById('search').value.toLowerCase();
    document.querySelectorAll('.job-row').forEach(row => {{
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
}}
</script>
</body></html>"""

    os.makedirs("results", exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML saved → {OUTPUT_HTML}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.utcnow()}] Starting job scrape...")
    seen = load_seen_jobs()
    all_saved = load_all_jobs()

    # Run all scrapers
    scrapers = [
        ("Indeed", scrape_indeed_rss),
        ("LinkedIn", scrape_linkedin_rss),
        ("RemoteOK", scrape_remoteok),
        ("Wellfound", scrape_wellfound),
        ("Glassdoor", scrape_glassdoor_rss),
        ("HN Who's Hiring", scrape_hn_whoishiring),
        ("Greenhouse (Direct)", scrape_greenhouse_boards),
        ("Lever (Direct)", scrape_lever_boards),
        ("Simplify", scrape_simplify),
        ("Google Careers", scrape_google_careers),
        ("Meta Careers", scrape_meta_careers),
        ("Amazon Careers", scrape_amazon_careers),
    ]

    fresh = []
    for name, fn in scrapers:
        try:
            results = fn()
            print(f"  {name}: {len(results)} jobs")
            fresh.extend(results)
        except Exception as e:
            print(f"  {name}: ERROR — {e}")

    print(f"Total raw: {len(fresh)}")

    # Dedup against seen
    seen_set = set(seen)
    saved_keys = {job_id(j["title"], j["company"]) for j in all_saved}
    new_jobs = []

    for job in fresh:
        jid = job_id(job["title"], job["company"])
        if jid not in seen_set and jid not in saved_keys:
            seen_set.add(jid)
            new_jobs.append(job)

    # Dedup within batch
    seen_batch = set()
    deduped = []
    for job in new_jobs:
        k = job_id(job["title"], job["company"])
        if k not in seen_batch:
            seen_batch.add(k)
            deduped.append(job)

    print(f"New unique jobs: {len(deduped)}")

    all_jobs = deduped + all_saved
    all_jobs = all_jobs[:MAX_JOBS_TO_SHOW]

    save_seen_jobs(list(seen_set))
    save_all_jobs(all_jobs)
    generate_html(all_jobs)

    print(f"Done. Board has {len(all_jobs)} total roles.")


if __name__ == "__main__":
    main()
