#!/usr/bin/env python3
"""Check the PRD under docs/prd/ against docs/charter.md and print derived tables.

Usage: python3 tools/prd_check.py [--trace] [--later] [--counts]

The PRD is docs/prd/prd.md plus every part file it links as `NN-name.md`, read
in the order the index lists them. A prd.md that links no part is checked as a
single file.

Checks (exit 1 on any failure):
  - every part the index lists exists, and every NN-*.md in docs/prd/ is listed
  - every requirement row cites at least one P-n and one FM-nn
  - every cited P, FM, C, D id exists in the charter
  - every Version cell is exactly "Initial" or "Later"
  - every R-<area>-<n> mentioned anywhere in the PRD is a live row or a retired id
  - no requirement id appears twice, within a file or across files

--trace  prints the traceability table (failure mode -> requirements, initial coverage)
--later  prints the ids marked Later
--counts prints row counts per area and version
"""
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRD_DIR = ROOT / "docs/prd"
INDEX = PRD_DIR / "prd.md"
CHARTER = ROOT / "docs/charter.md"

ROW_RE = re.compile(r"^\|\s*(R-[A-Z0-9]+-\d+)\s*\|(.*)\|\s*$")
ID_RE = re.compile(r"\b(P\d{1,2}|FM-\d{2}|C\d{1,2}|D\d{1,2})\b")
REF_RE = re.compile(r"\bR-(?:T|I|H|O|F|S\d)-\d+\b")
PART_LINK_RE = re.compile(r"\]\((\d{2}-[A-Za-z0-9-]+\.md)\)")
PART_NAME_RE = re.compile(r"^\d{2}-[A-Za-z0-9-]+\.md$")
RETIRED_RE = re.compile(r"^#{1,3} [^\n]*Retired[^\n]*$(.*?)(?=^#{1,3} |\Z)", re.M | re.S)


def charter_ids(text):
    ids = set()
    ids |= {f"P{n}" for n in re.findall(r"\*\*P(\d+)\.", text)}
    ids |= set(re.findall(r"^\| (FM-\d{2}) \|", text, re.M))
    ids |= set(re.findall(r"\*\*(C\d{1,2})\.", text))
    ids |= set(re.findall(r"\*\*(D\d+)\.", text))
    return ids


LABELS = {
    "FM-01": "Abstraction", "FM-02": "Load-bearing hack", "FM-03": "Style and pattern",
    "FM-04": "Tech debt mixing", "FM-05": "Scope creep", "FM-06": "Jumps to implementation",
    "FM-07": "Question noise", "FM-08": "Missing scenarios", "FM-09": "Parallel fatigue",
    "FM-10": "Unreviewable diff", "FM-11": "Filler tests", "FM-12": "Filler comments",
    "FM-13": "Missing comments", "FM-14": "Unknown impact", "FM-15": "Contract drift",
    "FM-16": "False rigor", "FM-17": "Memory rot", "FM-18": "Agent-only review",
    "FM-19": "Slow failure", "FM-20": "Hallucinated dependency", "FM-21": "State loss",
    "FM-22": "Loop drift", "FM-23": "Unsafe execution", "FM-24": "Data-boundary breach",
    "FM-25": "Stale approval",
}


def fm_names(text):
    out = {}
    for m in re.finditer(r"^\| (FM-\d{2}) \|", text, re.M):
        out[m.group(1)] = LABELS.get(m.group(1), "")
    return out


def load_prd(errors):
    """Return [(file name, text)]: prd.md first, then the parts it links, in index order."""
    index = INDEX.read_text(encoding="utf-8")
    names = []
    for m in PART_LINK_RE.finditer(index):
        if m.group(1) not in names:
            names.append(m.group(1))
    docs = [("prd.md", index)]
    for name in names:
        path = PRD_DIR / name
        if path.exists():
            docs.append((name, path.read_text(encoding="utf-8")))
        else:
            errors.append(f"prd.md lists {name}, which does not exist")
    for path in sorted(PRD_DIR.glob("*.md")):
        if PART_NAME_RE.match(path.name) and path.name not in names:
            errors.append(f"{path.name} is not listed in prd.md")
    return docs


def parse_rows(docs, errors):
    rows = OrderedDict()
    for name, text in docs:
        for line in text.splitlines():
            m = ROW_RE.match(line)
            if not m:
                continue
            rid = m.group(1)
            if rid in rows:
                errors.append(f"{rid}: duplicate id ({rows[rid]['file']} and {name})")
                continue
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) < 4:
                continue
            rows[rid] = {"text": cells[0], "cites": cells[1], "version": cells[2], "verify": cells[3], "line": line, "file": name}
    return rows


def retired_ids(docs):
    out = set()
    for _, text in docs:
        for m in RETIRED_RE.finditer(text):
            for line in m.group(1).splitlines():
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 2:
                    for i in range(0, len(cells), 2):
                        if REF_RE.fullmatch(cells[i]):
                            out.add(cells[i])
    return out


def main(argv):
    errors = []
    docs = load_prd(errors)
    prd = "\n".join(text for _, text in docs)
    charter = CHARTER.read_text(encoding="utf-8")
    valid = charter_ids(charter)
    rows = parse_rows(docs, errors)
    retired = retired_ids(docs)

    for rid, r in rows.items():
        cited = ID_RE.findall(r["cites"])
        if not any(c.startswith("P") for c in cited):
            errors.append(f"{rid}: no principle cited")
        if not any(c.startswith("FM") for c in cited):
            errors.append(f"{rid}: no failure mode cited")
        for c in cited:
            if c not in valid:
                errors.append(f"{rid}: unknown charter id {c}")
        if r["version"] not in ("Initial", "Later"):
            errors.append(f"{rid}: version cell is '{r['version']}'")

    for ref in sorted(set(REF_RE.findall(prd))):
        if ref not in rows and ref not in retired:
            errors.append(f"reference to {ref} which is neither a row nor retired")
    for ref in sorted(retired & set(rows)):
        errors.append(f"{ref} is both retired and a live row")

    if "--trace" in argv:
        names = fm_names(charter)
        by_fm = defaultdict(list)
        for rid, r in rows.items():
            for c in ID_RE.findall(r["cites"]):
                if c.startswith("FM"):
                    by_fm[c].append(rid)
        print("| Failure mode | Requirements | Initial |")
        print("|---|---|---|")
        for fm in sorted(names):
            ids = by_fm.get(fm, [])
            initial = [i for i in ids if rows[i]["version"] == "Initial"]
            later = [i for i in ids if rows[i]["version"] == "Later"]
            if not ids:
                cov = "None"
            elif not initial:
                cov = "No, all Later"
            elif later:
                cov = f"Yes; Later: {', '.join(later)}"
            else:
                cov = "Yes"
            print(f"| {fm} {names[fm]} | {', '.join(ids)} | {cov} |")

    if "--later" in argv:
        print(", ".join(rid for rid, r in rows.items() if r["version"] == "Later"))

    if "--counts" in argv:
        areas = defaultdict(lambda: [0, 0])
        for rid, r in rows.items():
            area = rid.split("-")[1]
            areas[area][0 if r["version"] == "Initial" else 1] += 1
        total_i = sum(v[0] for v in areas.values())
        total_l = sum(v[1] for v in areas.values())
        for a, (i, l) in areas.items():
            print(f"{a}: {i} Initial, {l} Later")
        print(f"total: {len(rows)} rows, {total_i} Initial, {total_l} Later, {len(retired)} retired ids")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"{len(errors)} problem(s)", file=sys.stderr)
        return 1
    files = "1 file" if len(docs) == 1 else f"{len(docs)} files"
    print(f"ok: {len(rows)} requirements in {files}, citations valid, versions binary", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
