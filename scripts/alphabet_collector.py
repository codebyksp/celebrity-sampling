#!/usr/bin/env python3
"""
scripts/alphabet_collector.py

Collect the first N celebrities per alphabet letter from whosdatedwho.com/popular?letter=<letter>

Usage:
    python scripts/alphabet_collector.py number_per_letter
"""
import argparse
import os
import logging
from urllib.parse import urljoin

import requests

import wd_utils as utils

logger = logging.getLogger("alphabet")

POPULAR_PATH = "/popular?letter="  # relative to BASE_URL

def fetch_letter_slugs(letter: str, count: int, session=None, seen_slugs=None):
    """
    Fetch the alphabet page for the given letter and return up to `count` individual slugs.
    """
    if session is None:
        session = requests
    if seen_slugs is None:
        seen_slugs = set()

    url = urljoin(utils.BASE_URL, POPULAR_PATH + letter)
    try:
        soup = utils.fetch_soup(url, session=session)
    except Exception as e:
        logger.warning("Failed to fetch letter page %s: %s", url, e)
        return []

    container = soup.select_one(".ff-box-grid")
    anchors = []
    if container:
        anchors = container.select("ul li a[href]")
    else:
        anchors = soup.select(".ff-grid-box.ff-list a[href], .ff-box-grid a[href], .ff-list a[href]")

    slugs = []
    for a in anchors:
        href = a.get("href")
        slug = utils.safe_slug_from_href(href)
        if not slug:
            continue
        if not utils.is_individual_slug(slug):
            continue
        if slug in seen_slugs:
            continue
        slugs.append(slug)
        seen_slugs.add(slug)
        if len(slugs) >= count:
            break

    if len(slugs) < count:
        logger.info("Letter %s: only found %d individual slugs (requested %d)", letter.upper(), len(slugs), count)
    else:
        logger.info("Letter %s: collected %d slugs", letter.upper(), len(slugs))
    utils.sleep_rate_limit()
    return slugs

def main():
    parser = argparse.ArgumentParser(description="Collect celebrities by alphabet from whosdatedwho.com")
    parser.add_argument("number_per_letter", type=int, help="Number of celebrities to collect per letter (e.g. 5)")
    parser.add_argument("--out", "-o", default=None, help="Output JSONL path (default: data/alphabet_<n>.jsonl)")
    args = parser.parse_args()

    n = args.number_per_letter
    if n <= 0:
        parser.error("number_per_letter must be > 0")

    utils.init_cache()
    session = requests

    if args.out:
        outpath = args.out
    else:
        os.makedirs(utils.DATA_DIR, exist_ok=True)
        outpath = os.path.join(utils.DATA_DIR, f"alphabet_{n}.jsonl")

    letters = [chr(ord("a") + i) for i in range(26)]
    all_slugs = []
    seen = set()
    logger.info("Collecting up to %d per letter (%d letters)", n, len(letters))
    for letter in letters:
        slugs = fetch_letter_slugs(letter, n, session=session, seen_slugs=seen)
        all_slugs.extend(slugs)
        logger.info("Total collected so far: %d", len(all_slugs))

    if not all_slugs:
        logger.error("No slugs collected; exiting.")
        return

    # write profiles (overwrite the output file for a fresh run)
    utils.write_profiles(all_slugs, outpath, session=session, append=False)

    logger.info("Done. Output written to %s (total records: %d)", outpath, len(all_slugs))

if __name__ == "__main__":
    main()
