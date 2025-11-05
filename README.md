# celebrity-sampling

COMP 370 — Homework 8: Data Sampling (WhosDatedWho)

## Overview
This repository implements two sampling strategies to collect celebrity data from **whosdatedwho.com**:

- **Snowball sampling** (`snowball_collector.py`): start from a seed celebrity and traverse past relationships until a target number of celebrities is collected.
- **Alphabet sampling** (`alphabet_collector.py`): for each letter A–Z, collect the first N celebrities whose names start with that letter.

The project also includes a comparison (`Comparison.md`) analyzing gender and age distributions between the two samples.

> **Important:** whosdatedwho.com does not provide a public API — scraping must be done respectfully. Use caching and rate-limiting.

---

## Repository structure
