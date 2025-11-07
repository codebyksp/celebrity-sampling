#!/usr/bin/env python3
"""
scripts/snowball_collector.py

Usage:
    python scripts/snowball_collector.py start_slug target_num

Example:
    python scripts/snowball_collector.py barbara-palvin 130
"""
import argparse
import os
import logging
from urllib.parse import urljoin

import requests

# import shared utilities from wd_utils (same folder)
import wd_utils as utils

# Logging
logger = logging.getLogger("snowball")

def find_dating_links_bfs(start_slug: str, target_num: int, session=None):
    """
    BFS from start_slug collecting unique celebrity slugs until target_num reached.
    Returns list of slugs discovered (in order).
    """
    if session is None:
        session = requests

    queue = [start_slug]
    visited = set()
    collected = []

    logger.info("Starting BFS at %s aiming for %d celebrities", start_slug, target_num)

    while queue and len(collected) < target_num:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        cur_url = urljoin(utils.BASE_URL, utils.CELEB_PATH + current)
        try:
            soup = utils.fetch_soup(cur_url, session=session)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", cur_url, e)
            continue

        partners = utils.parse_partners_from_history(soup)
        logger.info("Discovered %d partners for %s", len(partners), current)

        if current not in collected:
            collected.append(current)

        for p in partners:
            if p not in visited and p not in queue and p not in collected:
                queue.append(p)

        logger.info("Collected: %d / %d ; Queue size: %d", len(collected), target_num, len(queue))
        utils.sleep_rate_limit()

        if not queue and len(collected) < target_num:
            logger.info("Queue exhausted before reaching target. Collected %d items.", len(collected))
            break

    return collected[:target_num]

def main():
    parser = argparse.ArgumentParser(description="Collect dating history of celebrities using snowball sampling.")
    parser.add_argument("start_slug", type=str, help="Starting celebrity slug (e.g. 'barbara-palvin').")
    parser.add_argument("target_num", type=int, help="Target number of celebrities to collect.")
    parser.add_argument("--out", "-o", default=None, help="Output JSONL path (default: data/<start_slug>_snowball.jsonl)")
    args = parser.parse_args()

    # initialize caching
    utils.init_cache()
    session = requests

    start_slug = args.start_slug.strip().lower().replace(" ", "-")

    if args.out:
        outpath = args.out
    else:
        os.makedirs(utils.DATA_DIR, exist_ok=True)
        outpath = os.path.join(utils.DATA_DIR, f"{start_slug}_snowball.jsonl")

    slugs = find_dating_links_bfs(start_slug, args.target_num, session=session)
    logger.info("Total slugs discovered: %d", len(slugs))

    # write profiles (append mode to preserve prior runs)
    utils.write_profiles(slugs, outpath, session=session, append=True)

    logger.info("All done — output written to %s", outpath)

if __name__ == "__main__":
    main()
