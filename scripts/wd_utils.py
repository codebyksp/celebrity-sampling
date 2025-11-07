#!/usr/bin/env python3
"""
scripts/wd_utils.py

Shared utilities for whosdatedwho scrapers:
- caching / network (requests-cache)
- html -> parsing helpers
- fetching a single profile -> normalized dict
- writing profile records to JSONL

Place this in the same folder as the collector scripts (scripts/).
"""
import os
import re
import time
import random
import json
import logging
from urllib.parse import urljoin, urlparse

import requests
import requests_cache
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration (shared)
# ---------------------------------------------------------------------------
BASE_URL = "https://www.whosdatedwho.com"
CELEB_PATH = "/dating/"

# repo-aware data/cache dirs (scripts/.. -> repo root)
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(REPO_ROOT, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
CACHE_BASEPATH = os.path.join(CACHE_DIR, "celebs_cache")
CACHE_EXPIRE = 60 * 60 * 24  # 1 day

RATE_LIMIT_MIN = 1.0
RATE_LIMIT_MAX = 2.5

# Logging (basic config)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("wd_utils")

# ---------------------------------------------------------------------------
# Network / cache
# ---------------------------------------------------------------------------

def init_cache():
    """Create cache dir and install requests-cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    requests_cache.install_cache(CACHE_BASEPATH, expire_after=CACHE_EXPIRE)
    logger.info("Requests cache installed at %s.sqlite (expire=%ds)", CACHE_BASEPATH, CACHE_EXPIRE)

def fetch_soup(url: str, session: requests.Session = None):
    """Fetch page and return BeautifulSoup. Raises on HTTP errors."""
    if session is None:
        session = requests
    headers = {"User-Agent": "COMP370-scraper/1.0 (+https://github.com/yourname/celebrity-sampling)"}
    logger.debug("Fetching %s", url)
    resp = session.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")

# ---------------------------------------------------------------------------
# Simple helpers / heuristics
# ---------------------------------------------------------------------------

def safe_slug_from_href(href: str):
    """
    Turn href into a slug candidate (e.g. '/dating/dylan-sprouse' -> 'dylan-sprouse').
    Returns None if href is empty or parsing fails.
    """
    if not href:
        return None
    parsed = urlparse(href)
    path = parsed.path if parsed.path else href
    path = path.strip("/")
    if not path:
        return None
    parts = path.split("/")
    if len(parts) >= 2 and parts[0].lower() == "dating":
        return parts[1]
    return parts[-1]

def is_individual_slug(slug: str) -> bool:
    """Heuristic to detect individual-person slugs (not couple pages)."""
    if not slug:
        return False
    s = slug.lower()
    if "-and-" in s:
        return False
    if s.startswith("and-") or s.endswith("-and"):
        return False
    if "couple" in s:
        return False
    return True

def sleep_rate_limit():
    """Polite random sleep between requests (configurable constants)."""
    time.sleep(random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX))

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_profile_table(soup: BeautifulSoup):
    """Parse profile table (First Name, Birthday, etc.) into dict."""
    data = {}
    table = None
    for t in soup.find_all("table"):
        if t.find(string=re.compile(r"First Name", re.I)):
            table = t
            break
    if not table:
        return data
    for tr in table.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) >= 2:
            key = tds[0].get_text(strip=True)
            val = tds[1].get_text(" ", strip=True)
            if key:
                data[key] = val
    return data

def parse_facts_block(soup: BeautifulSoup):
    """Parse small facts like Age and Relationships total."""
    facts = {}
    age_box = soup.select_one(".ff-fact-box.small.age .fact")
    if age_box:
        text = age_box.get_text(strip=True)
        if text.isdigit():
            facts["age"] = int(text)
        else:
            m = re.search(r"(\d+)", text)
            if m:
                facts["age"] = int(m.group(1))

    rel_box = soup.select_one(".ff-fact-box.small.relationships .fact")
    if rel_box:
        text = rel_box.get_text(strip=True)
        m = re.search(r"(\d+)", text)
        if m:
            facts["relationships_total"] = int(m.group(1))
    return facts

def infer_gender_from_about(soup: BeautifulSoup):
    """Simple heuristic to infer gender from the about paragraph."""
    p = soup.select_one("p.ff-auto-about")
    if not p:
        return "unknown"
    text = p.get_text(" ", strip=True).lower()
    if re.search(r"\b(she|her)\b", text):
        return "female"
    if re.search(r"\b(he|his)\b", text):
        return "male"
    if re.search(r"\bactress\b", text):
        return "female"
    if re.search(r"\bactor\b", text) and not re.search(r"\bactress\b", text):
        return "male"
    return "unknown"

def parse_partners_from_history(soup: BeautifulSoup):
    """
    Parse partner slugs from the dating-history grid/list.
    Returns unique individual slugs preserving discovery order.
    """
    partners = []
    container = soup.find(id="ff-dating-history")
    if not container:
        container = soup.find(id="ff-dating-history-grid")
    if not container:
        container = soup.find(class_=re.compile(r"ff-dating-history|ff-grid|dating-history"))
    if not container:
        return partners

    for a in container.find_all("a", href=True):
        href = a["href"].strip()
        slug = safe_slug_from_href(href)
        if not slug:
            continue
        if not is_individual_slug(slug):
            continue
        partners.append(slug)

    seen = set()
    unique = []
    for p in partners:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique

def parse_name_and_slug(soup: BeautifulSoup, url: str):
    """
    Derive canonical name and slug from the page.
    Returns (name, slug).
    """
    name = None
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        name = h1.get_text(strip=True)
    title_tag = soup.title
    if not name and title_tag:
        t = title_tag.get_text(" ", strip=True)
        name = re.sub(r"\s*-\s*Who's Dated Who.*$", "", t, flags=re.I).strip()
    if not name:
        candidate = soup.select_one(".ff-profile .ff-title, .ff-title")
        if candidate:
            name = candidate.get_text(strip=True)
    if not name:
        slug = safe_slug_from_href(url)
        if slug:
            name = slug.replace("-", " ").title()
        else:
            name = "unknown"
    slug = safe_slug_from_href(url)
    return name, slug

# ---------------------------------------------------------------------------
# Profile fetcher + writer
# ---------------------------------------------------------------------------

def fetch_profile(slug: str, session=None):
    """
    Fetch a single celebrity profile page and return a normalized dict
    (or None on failure).
    """
    if session is None:
        session = requests
    url = urljoin(BASE_URL, CELEB_PATH + slug)
    try:
        soup = fetch_soup(url, session=session)
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    name, canonical_slug = parse_name_and_slug(soup, url)
    facts = parse_facts_block(soup)
    profile_table = parse_profile_table(soup)
    gender = infer_gender_from_about(soup)
    partners = parse_partners_from_history(soup)

    item = {
        "slug": canonical_slug or slug,
        "url": url,
        "name": name,
        "age": facts.get("age"),
        "relationships_total": facts.get("relationships_total"),
        "gender_inferred": gender,
        "partners": partners,
        "profile_table": profile_table,
    }
    return item

def write_profiles(slugs, outpath, session=None, append=False):
    """
    Fetch profiles for each slug and write JSON lines to outpath.
    If append==True, append to file; otherwise overwrite.
    Returns number of successfully written records.
    """
    if session is None:
        session = requests
    mode = "a" if append else "w"
    dirpath = os.path.dirname(outpath)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    written = 0
    with open(outpath, mode, encoding="utf-8") as fh:
        for slug in slugs:
            item = fetch_profile(slug, session=session)
            if item is None:
                continue
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            written += 1
            logger.info("Wrote %s (age=%s, rels=%s, partners=%d)", item.get("slug"), item.get("age"), item.get("relationships_total"), len(item.get("partners", [])))
            sleep_rate_limit()
    logger.info("Finished writing %d records to %s", written, outpath)
    return written
