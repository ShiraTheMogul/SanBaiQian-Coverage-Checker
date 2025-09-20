#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable, Tuple

# --- Unicode range helpers ----------------------------------------------------
# Covers the main Han ranges used in modern and historical texts.
HAN_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x20000, 0x2A6DF), # CJK Unified Ideographs Extension B
    (0x2A700, 0x2B73F), # Extension C
    (0x2B740, 0x2B81F), # Extension D
    (0x2B820, 0x2CEAF), # Extension E
    (0x2CEB0, 0x2EBEF), # Extension F
    (0x30000, 0x3134F), # Extension G
    (0x31350, 0x323AF), # Extension H (as of Unicode 15+)
    (0x2EBF0, 0x2EE5D), # Extension I
    (0x323B0, 0x33479), # Extension J
)

def is_han(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    for start, end in HAN_RANGES:
        if start <= cp <= end:
            return True
    return False

# --- Core logic ----------------------------------------------------------------

def load_inventory(path: Path) -> set[str]:
    """Load inventory file and return a set of characters.

    The file can be a single long line of characters or multiple lines.
    Whitespace is ignored.
    """
    data = path.read_text(encoding="utf-8")
    inv_chars = {ch for ch in data if is_han(ch)}
    return inv_chars


def load_inventories(paths: Iterable[Path]) -> dict[str, set[str]]:
    """Load multiple inventory files, keyed by filename stem."""
    inventories: dict[str, set[str]] = {}
    for p in paths:
        label = p.stem or str(p)
        base = label
        n = 2
        while label in inventories:
            label = f"{base}-{n}"
            n += 1
        inventories[label] = load_inventory(p)
    return inventories


def iter_text_chars(text: str, han_only: bool = True) -> Iterable[str]:
    for ch in text:
        if han_only and not is_han(ch):
            continue
        if ch.strip() == "":  # skip whitespace
            continue
        yield ch


def coverage_report(
    text: str,
    inventory: set[str],
    han_only: bool = True,
) -> dict:
    """Return a dict with coverage metrics and frequency tables."""
    chars = list(iter_text_chars(text, han_only=han_only))
    total = len(chars)

    known = [ch for ch in chars if ch in inventory]
    unknown = [ch for ch in chars if ch not in inventory]

    known_count = len(known)
    unknown_count = len(unknown)
    coverage = (known_count / total * 100.0) if total else 100.0

    return {
        "total_chars": total,
        "known_chars": known_count,
        "unknown_chars": unknown_count,
        "coverage_pct": coverage,
        "known_freq": Counter(known),
        "unknown_freq": Counter(unknown),
    }


def per_line_breakdown(
    text: str,
    inventory: set[str],
    han_only: bool = True,
) -> list[tuple[int, int, int, float, str]]:
    """
    Return per-line coverage as a list of tuples:
        (line_no, total, known, coverage_pct, line_text)
    Only Han characters (or all characters if han_only=False) are counted.
    """
    results = []
    for i, line in enumerate(text.splitlines(), start=1):
        chars = list(iter_text_chars(line, han_only=han_only))
        total = len(chars)
        if total == 0:
            results.append((i, 0, 0, 100.0, line.rstrip("\n")))
            continue
        known = sum(1 for ch in chars if ch in inventory)
        pct = known / total * 100.0
        results.append((i, total, known, pct, line.rstrip("\n")))
    return results


# --- Pretty printing helpers ---------------------------------------------------

def human_int(n: int) -> str:
    return f"{n:,}"


def print_stats_block(title: str, rep: dict) -> None:
    print(f"\n=== {title} ===")
    print(f"Total counted chars: {human_int(rep['total_chars'])}")
    print(f"Known (in-inventory): {human_int(rep['known_chars'])}")
    print(f"Unknown (OOV): {human_int(rep['unknown_chars'])}")
    print(f"Coverage: {rep['coverage_pct']:.2f}%")


def print_oov_list(rep: dict) -> None:
    if rep["unknown_chars"] == 0:
        print("\nNo unknown characters. 🎉")
        return
    unique_oov = list(rep["unknown_freq"].keys())
    # Order by frequency desc then by codepoint for stability
    unique_oov.sort(key=lambda ch: (-rep["unknown_freq"][ch], ord(ch)))
    print("\nList of characters not present (unique OOV, freq-desc):")
    print("".join(unique_oov))


def print_oov_frequency(rep: dict, top_n: int) -> None:
    if rep["unknown_chars"] == 0:
        return
    # High-frequency (top N)
    print(f"\nTop {top_n} unknown characters (high frequency):")
    for ch, cnt in rep["unknown_freq"].most_common(top_n):
        code = f"U+{ord(ch):04X}"
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = "<unnamed>"
        print(f"{ch}\t{cnt}\t{code}\t{name}")

    # Low-frequency (bottom N)
    items = list(rep["unknown_freq"].items())
    items.sort(key=lambda kv: (kv[1], ord(kv[0])))
    bottom = items[:top_n]
    print(f"\nBottom {top_n} unknown characters (low frequency):")
    for ch, cnt in bottom:
        code = f"U+{ord(ch):04X}"
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = "<unnamed>"
        print(f"{ch}\t{cnt}\t{code}\t{name}")


# --- Programmatic API (import-friendly) --------------------------------------

def build_report_text(
    text: str,
    inventories: dict[str, set[str]],
    *,
    union: bool = False,
    top_unknown: int = 15,
    han_only: bool = True,
    per_line: bool = False,
) -> str:
    lines: list[str] = []

    # Compute reports
    reports: dict[str, dict] = {
        label: coverage_report(text, inv, han_only=han_only)
        for label, inv in inventories.items()
    }

    union_report = None
    union_set = None
    if union and len(inventories) > 1:
        union_set = set().union(*inventories.values())
        union_report = coverage_report(text, union_set, han_only=han_only)

    # Header
    lines.append("=== Inventories Loaded ===")
    for label, inv in inventories.items():
        lines.append(f"- {label}: {human_int(len(inv))} characters")
    if union_report is not None:
        lines.append(
            f"- <union>: {human_int(sum(len(inv) for inv in inventories.values()))} "
            f"(raw sum; union unique size {human_int(len(union_set))})"
        )

    # Per-inventory results
    for label, rep in reports.items():
        lines.append(f"\n=== Results for [{label}] ===")
        lines.append(f"Total counted chars: {human_int(rep['total_chars'])}")
        lines.append(f"Known (in-inventory): {human_int(rep['known_chars'])}")
        lines.append(f"Unknown (OOV): {human_int(rep['unknown_chars'])}")
        lines.append(f"Coverage: {rep['coverage_pct']:.2f}%")

        if rep["unknown_chars"]:
            unique_oov = list(rep["unknown_freq"].keys())
            unique_oov.sort(key=lambda ch: (-rep["unknown_freq"][ch], ord(ch)))
            lines.append("\nList of characters not present (unique OOV, freq-desc):")
            lines.append("".join(unique_oov))

            # High-frequency
            lines.append(f"\nTop {top_unknown} unknown characters (high frequency):")
            for ch, cnt in rep["unknown_freq"].most_common(top_unknown):
                code = f"U+{ord(ch):04X}"
                try:
                    name = unicodedata.name(ch)
                except ValueError:
                    name = "<unnamed>"
                lines.append(f"{ch}\t{cnt}\t{code}\t{name}")

            # Low-frequency
            items = sorted(rep["unknown_freq"].items(), key=lambda kv: (kv[1], ord(kv[0])))
            bottom = items[:top_unknown]
            lines.append(f"\nBottom {top_unknown} unknown characters (low frequency):")
            for ch, cnt in bottom:
                code = f"U+{ord(ch):04X}"
                try:
                    name = unicodedata.name(ch)
                except ValueError:
                    name = "<unnamed>"
                lines.append(f"{ch}\t{cnt}\t{code}\t{name}")
        else:
            lines.append("\nNo unknown characters. 🎉")

        if per_line:
            lines.append("\nPer-line coverage:")
            for line_no, total, known, pct, line in per_line_breakdown(
                text, inventories[label], han_only=han_only
            ):
                lines.append(f"{line_no:>4}: {known:>4}/{total:<4} {pct:6.2f}% | {line}")

    # Union block
    if union_report is not None:
        rep = union_report
        lines.append("\n=== Results for [UNION of inventories] ===")
        lines.append(f"Total counted chars: {human_int(rep['total_chars'])}")
        lines.append(f"Known (in-inventory): {human_int(rep['known_chars'])}")
        lines.append(f"Unknown (OOV): {human_int(rep['unknown_chars'])}")
        lines.append(f"Coverage: {rep['coverage_pct']:.2f}%")
        if rep["unknown_chars"]:
            unique_oov = list(rep["unknown_freq"].keys())
            unique_oov.sort(key=lambda ch: (-rep["unknown_freq"][ch], ord(ch)))
            lines.append("\nList of characters not present (unique OOV, freq-desc):")
            lines.append("".join(unique_oov))

            lines.append(f"\nTop {top_unknown} unknown characters (high frequency):")
            for ch, cnt in rep["unknown_freq"].most_common(top_unknown):
                code = f"U+{ord(ch):04X}"
                try:
                    name = unicodedata.name(ch)
                except ValueError:
                    name = "<unnamed>"
                lines.append(f"{ch}\t{cnt}\t{code}\t{name}")

            items = sorted(rep["unknown_freq"].items(), key=lambda kv: (kv[1], ord(kv[0])))
            bottom = items[:top_unknown]
            lines.append(f"\nBottom {top_unknown} unknown characters (low frequency):")
            for ch, cnt in bottom:
                code = f"U+{ord(ch):04X}"
                try:
                    name = unicodedata.name(ch)
                except ValueError:
                    name = "<unnamed>"
                lines.append(f"{ch}\t{cnt}\t{code}\t{name}")
        else:
            lines.append("\nNo unknown characters under union. 🎉")

    return "\n".join(lines)


def run_analysis_from_files(
    inventory_paths: list[Path],
    input_path: Path,
    *,
    union: bool = False,
    top_unknown: int = 15,
    han_only: bool = True,
    per_line: bool = False,
) -> str:
    """Load files and return the plain-text report."""
    inventories = load_inventories(inventory_paths)
    text = input_path.read_text(encoding="utf-8")
    return build_report_text(
        text,
        inventories,
        union=union,
        top_unknown=top_unknown,
        han_only=han_only,
        per_line=per_line,
    )


def save_report(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")

# --- CLI ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Evaluate Han-character comprehensibility against one or more inventories "
            "(e.g., 三百千 + Simplified)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "-i",
        "--inventory",
        type=Path,
        nargs="+",
        default=[Path("inventory_traditional.txt")],
        help=(
            "Path(s) to inventory file(s). You can pass multiple files "
            "(e.g., classical and simplified)."
        ),
    )
    p.add_argument(
        "--input",
        type=Path,
        help="Path to input text. If omitted, read from STDIN.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path to write a plain-text report file.",
    )
    p.add_argument(
        "--all-chars",
        action="store_true",
        help="Count all characters (not just Han) in totals.",
    )
    p.add_argument(
        "--per-line",
        action="store_true",
        help="Show per-line coverage breakdown.",
    )
    p.add_argument(
        "--top-unknown",
        type=int,
        default=15,
        help="Top-N for high- and low-frequency OOV lists (both use this value).",
    )
    p.add_argument(
        "--union",
        action="store_true",
        help=(
            "If multiple inventories are provided, report the union coverage "
            "(any inventory match counts as known). Default is to show each inventory separately"
        ),
    )
    args = p.parse_args(argv)

    # Validate inventories
    missing = [str(pth) for pth in args.inventory if not pth.exists()]
    if missing:
        p.error("Inventory file(s) not found: " + ", ".join(missing))

    inventories = load_inventories(args.inventory)

    # Read input text
    if args.input is None:
        text = sys.stdin.read()
    else:
        if not args.input.exists():
            p.error(f"Input file not found: {args.input}")
        text = args.input.read_text(encoding="utf-8")

    # Compute reports
    reports: dict[str, dict] = {}
    for label, inv in inventories.items():
        reports[label] = coverage_report(text, inv, han_only=not args.all_chars)

    # Optionally union inventory
    union_report = None
    if args.union and len(inventories) > 1:
        union_set = set().union(*inventories.values())
        union_report = coverage_report(text, union_set, han_only=not args.all_chars)

    
# --- OUTPUT SECTION -------------------------------------------------------
    # Build one consolidated report text so it can be printed and/or saved.
    consolidated = build_report_text(
        text,
        inventories,
        union=args.union,
        top_unknown=args.top_unknown,
        han_only=not args.all_chars,
        per_line=args.per_line,
    )
    print(consolidated)

    # If user asked for a file, write it.
    if args.output is not None:
        try:
            save_report(args.output, consolidated)
            print(f"[Saved report to: {args.output}]")
        except Exception as e:
            print(f"[Error writing report to {args.output}: {e}]")

    return 0



if __name__ == "__main__":
    raise SystemExit(main())
