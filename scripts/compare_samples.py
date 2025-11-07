#!/usr/bin/env python3
"""
scripts/compare_samples.py

Compare two samples (JSONL produced by snowball_collector.py and alphabet_collector.py).

Outputs:
 - Console summary of gender distribution and age statistics for each sample.
 - Markdown file (Comparison.md) with two sections: Gender and Age.

Usage:
    python scripts/compare_samples.py \
        --snow data/barbara-palvin_snowball.jsonl \
        --alpha data/alphabet_5.jsonl \
        --out data/Comparison.md

If --out is omitted, writes ./Comparison.md in the current working dir.
"""
import argparse
import json
import os
import re
from collections import Counter, defaultdict
from statistics import mean, median, stdev
from typing import List, Dict, Any, Tuple, Optional

# ------- helpers -------

def read_jsonl(path: str):
    """Yield JSON objects from a .jsonl file (skip malformed lines)."""
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # skip malformed lines but continue
                print(f"Warning: failed to parse JSON on {path}:{lineno}")
                continue

def normalize_gender(g: Optional[str]) -> str:
    """Normalize common gender strings to 'male','female','unknown'."""
    if g is None:
        return "unknown"
    s = str(g).strip().lower()
    if s in ("male", "m", "man"):
        return "male"
    if s in ("female", "f", "woman", "girl"):
        return "female"
    # sometimes words like 'unknown', '' etc.
    if s in ("unknown", "n/a", ""):
        return "unknown"
    # heuristics for pronoun-like input
    if re.search(r"\b(she|her|woman|female)\b", s):
        return "female"
    if re.search(r"\b(he|his|him|man|male)\b", s):
        return "male"
    # fallback
    return "unknown"

def extract_age(val) -> Optional[int]:
    """
    Extract integer age if possible.
    Accepts int or string with digits.
    Returns None if not parseable.
    """
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    s = str(val).strip()
    if not s:
        return None
    # sometimes age is like "32" or "32 yrs" or "Born 1990"
    # first try pure int
    if s.isdigit():
        return int(s)
    m = re.search(r"(\d{1,3})", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None

def analyze_records(records: List[Dict[str,Any]]) -> Dict[str,Any]:
    """
    Given a list of profile dicts, returns:
      - total_count
      - gender_counts (Counter)
      - age_stats: list of ages, mean, median, stdev (stdev only if >=2)
    """
    genders = Counter()
    ages = []
    for rec in records:
        # fields where gender might be stored
        gender = None
        # preferred field names
        for key in ("gender_inferred", "gender", "sex"):
            if key in rec:
                gender = rec.get(key)
                break
        genders[normalize_gender(gender)] += 1

        # age extraction: common field 'age' or inside profile_table 'Birthday' parse not attempted here
        raw_age = rec.get("age")
        age = extract_age(raw_age)
        if age is None:
            # try profile_table Birthday -> sometimes contains birth date rather than age
            pt = rec.get("profile_table") or {}
            bday = pt.get("Birthday") or pt.get("Birth Date") or pt.get("Born")
            # try to extract age from birthday string if it contains digits that look like age (rare)
            maybe_age = extract_age(bday)
            if maybe_age is not None and maybe_age > 0 and maybe_age < 120:
                ages.append(maybe_age)
        else:
            ages.append(age)

    stats = {}
    total = len(records)
    stats["total"] = total
    stats["gender_counts"] = dict(genders)
    stats["n_with_age"] = len(ages)
    stats["ages"] = ages
    if ages:
        stats["age_mean"] = mean(ages)
        stats["age_median"] = median(ages)
        stats["age_min"] = min(ages)
        stats["age_max"] = max(ages)
        if len(ages) >= 2:
            stats["age_stdev"] = stdev(ages)
        else:
            stats["age_stdev"] = None
    else:
        stats["age_mean"] = stats["age_median"] = stats["age_min"] = stats["age_max"] = stats["age_stdev"] = None

    return stats

def format_gender_table(counter: Dict[str,int], total: int) -> str:
    lines = []
    lines.append("| Gender | Count | Percent |")
    lines.append("|---:|---:|---:|")
    for k in ("male","female","unknown"):
        c = counter.get(k, 0)
        pct = (c / total * 100) if total>0 else 0.0
        lines.append(f"| {k.title()} | {c} | {pct:.1f}% |")
    return "\n".join(lines)

def format_age_table(stats: Dict[str,Any]) -> str:
    if stats["n_with_age"] == 0:
        return "No age data available in this sample."
    lines = []
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Records with age | {stats['n_with_age']} |")
    lines.append(f"| Mean age | {stats['age_mean']:.2f} |")
    lines.append(f"| Median age | {stats['age_median']:.2f} |")
    if stats['age_stdev'] is not None:
        lines.append(f"| Age stdev | {stats['age_stdev']:.2f} |")
    lines.append(f"| Min age | {stats['age_min']} |")
    lines.append(f"| Max age | {stats['age_max']} |")
    return "\n".join(lines)

# ------- main CLI -------

def main():
    parser = argparse.ArgumentParser(description="Compare two celebrity samples (gender distribution and age).")
    parser.add_argument("--snow", required=True, help="Path to snowball JSONL file (e.g. data/<slug>_snowball.jsonl)")
    parser.add_argument("--alpha", required=True, help="Path to alphabet JSONL file (e.g. data/alphabet_5.jsonl)")
    parser.add_argument("--out", default="Comparison.md", help="Output markdown file (default: Comparison.md)")
    args = parser.parse_args()

    # Read records
    snow_records = list(read_jsonl(args.snow))
    alpha_records = list(read_jsonl(args.alpha))

    snow_stats = analyze_records(snow_records)
    alpha_stats = analyze_records(alpha_records)

    # Console summary
    def print_summary(name: str, stats: Dict[str,Any]):
        print("="*60)
        print(f"Sample: {name}")
        print(f"Total records: {stats['total']}")
        print("Gender distribution:")
        for k in ("male","female","unknown"):
            c = stats["gender_counts"].get(k, 0)
            pct = (c / stats["total"] * 100) if stats["total"]>0 else 0.0
            print(f"  {k.title():7s}: {c:4d} ({pct:5.1f}%)")
        print("Age summary (records with age):")
        if stats["n_with_age"] == 0:
            print("  No age data found.")
        else:
            print(f"  n={stats['n_with_age']}  mean={stats['age_mean']:.2f}  median={stats['age_median']:.2f}  std={stats['age_stdev'] if stats['age_stdev'] is not None else 'NA'}")
        print()

    print_summary("Snowball", snow_stats)
    print_summary("Alphabet", alpha_stats)

    # Write Comparison.md
    md_lines = []
    md_lines.append("# Comparison of Samples")
    md_lines.append("")
    md_lines.append("## Gender")
    md_lines.append("")
    md_lines.append(f"### Snowball sample (total records: {snow_stats['total']})")
    md_lines.append("")
    md_lines.append(format_gender_table(snow_stats["gender_counts"], snow_stats["total"]))
    md_lines.append("")
    md_lines.append(f"### Alphabet sample (total records: {alpha_stats['total']})")
    md_lines.append("")
    md_lines.append(format_gender_table(alpha_stats["gender_counts"], alpha_stats["total"]))
    md_lines.append("")
    md_lines.append("## Age")
    md_lines.append("")
    md_lines.append(f"### Snowball sample (n with age: {snow_stats['n_with_age']})")
    md_lines.append("")
    md_lines.append(format_age_table(snow_stats))
    md_lines.append("")
    md_lines.append(f"### Alphabet sample (n with age: {alpha_stats['n_with_age']})")
    md_lines.append("")
    md_lines.append(format_age_table(alpha_stats))
    md_lines.append("")
    md_lines.append("## Notes")
    md_lines.append("")
    md_lines.append("- Gender is inferred using the `gender_inferred` field when present. Values were normalized to 'male', 'female', or 'unknown'.")
    md_lines.append("- Age is taken from the `age` field when available; records without a parseable age were excluded from the age statistics.")
    md_lines.append("- If a sample has few or no age values, mean/stdev may be unavailable.")
    md_text = "\n".join(md_lines)

    # ensure output dir exists
    outdir = os.path.dirname(args.out)
    if outdir:
        os.makedirs(outdir, exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(md_text)

    print(f"Wrote comparison markdown to {args.out}")

if __name__ == "__main__":
    main()
