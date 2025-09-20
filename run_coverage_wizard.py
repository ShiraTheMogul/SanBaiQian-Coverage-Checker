#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple interactive wizard for sanbaiqian_coverage_fixed.py
Defaults:
- inventory_traditional.txt
- my_text.txt
- Han-only (no --all-chars)
- no UNION
- top-15
- coverage_report.txt
"""
import subprocess, shlex, sys
from pathlib import Path

def ask(prompt, default=None):
    if default is not None:
        p = f"{prompt} [{default}]: "
    else:
        p = f"{prompt}: "
    try:
        val = input(p).strip()
    except EOFError:
        val = ""
    return val or (default if default is not None else "")

def yesno(prompt, default=False):
    d = "Y/n" if default else "y/N"
    while True:
        ans = ask(f"{prompt} ({d})").lower()
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please answer y or n.")

def main():
    here = Path(__file__).resolve().parent
    script_path = here / "sanbaiqian_coverage.py"
    if not script_path.exists():
        given = ask("Path to sanbaiqian_coverage.py", str(script_path))
        script_path = Path(given).expanduser().resolve()
    if not script_path.exists():
        print(f"Error: Script not found at {script_path}")
        sys.exit(1)

    # Default files
    default_inv = here / "inventory_traditional.txt"
    default_text = here / "my_text.txt"
    default_out = here / "coverage_report.txt"

    inv_paths = [str(default_inv.resolve())] if default_inv.exists() else []
    input_text = str(default_text.resolve()) if default_text.exists() else ""
    output_file = str(default_out.resolve())

    # Prompt user but with these defaults
    inventories = ask("Inventory file(s), comma-separated", ",".join(inv_paths))
    inv_paths = [str(Path(p.strip()).expanduser().resolve()) for p in inventories.split(",") if p.strip()]

    input_text = ask("Path to the input text", input_text)
    output_file = ask("Path to save the report (leave blank to skip)", output_file)

    union = yesno("Treat multiple inventories as a UNION (any match counts as known)?", default=False)
    per_line = yesno("Show per-line breakdown?", default=False)
    all_chars = yesno("Include non-Han characters in counts (i.e., not Han-only)?", default=False)
    try:
        top_unknown = int(ask("Top-N unknown characters to list", "15"))
    except ValueError:
        top_unknown = 15

    # Build command
    cmd = [sys.executable, str(script_path), "-i"]
    if inv_paths:
        cmd.extend(inv_paths)
    if input_text:
        cmd.extend(["--input", str(Path(input_text).expanduser().resolve())])
    if output_file:
        if output_file.strip():
            cmd.extend(["-o", str(Path(output_file).expanduser().resolve())])
    if all_chars:
        cmd.append("--all-chars")
    if per_line:
        cmd.append("--per-line")
    if union:
        cmd.append("--union")
    if top_unknown and top_unknown != 15:
        cmd.extend(["--top-unknown", str(top_unknown)])

    print("\nRunning command:\n", " ".join(shlex.quote(c) for c in cmd), "\n")
    subprocess.run(cmd, text=True)

if __name__ == "__main__":
    main()
