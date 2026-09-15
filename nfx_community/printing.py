import sys
from collections import Counter


def print_header(title):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def print_gap_row(label, repo_list):
    total = len(repo_list)
    in_cat = sum(1 for r in repo_list if r["in_catalog"])
    missing = total - in_cat
    print(f"  {label:<28} {total:>6}  {in_cat:>11}  {missing:>14}")


def progress_bar(current, total, prefix=""):
    if total == 0:
        return
    pct = current / total
    bar_len = 30
    filled = int(bar_len * pct)
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
    sys.stdout.write(f"\r{prefix}[{bar}] {current}/{total} ({pct * 100:.0f}%)")
    sys.stdout.flush()
    if current == total:
        sys.stdout.write("\n")


def print_skip_summary(skip_counter, n_empty=0, parse_fail_count=0):
    skip_total = sum(skip_counter.values())
    if skip_total:
        print(f"  Skipped processes: {skip_total}")
        for reason in ("failed_parsing", "version_printer", "no_tools"):
            c = skip_counter.get(reason, 0)
            if c:
                print(f"    {reason:20s} {c}")
    if parse_fail_count:
        print(f"  bashlex parse failures:        {parse_fail_count}")
