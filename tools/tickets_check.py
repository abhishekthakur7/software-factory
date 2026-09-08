#!/usr/bin/env python3
"""Check the build tickets under docs/design/tickets/ against the PRD and the milestone map.

Usage: python3 tools/tickets_check.py [--list] [--counts]

The tickets are docs/design/tickets/A.md, AB.md and B.md, one file per milestone,
indexed by docs/design/TICKETS.md. A file that does not exist yet is skipped; a
file that exists must be listed in the index. Rows come from the PRD
(tools/prd_check.py reads it) and the row-to-milestone map from Appendix A of
docs/design/milestones.md.

Checks (exit 1 on any failure):
  - every ticket has the sections id, title, milestone, blocks, HLD components,
    depends on, rows covered, description, scope (in and out), acceptance
    criteria and verification, none empty
  - ticket ids are T-<milestone>-NN, numbered 01, 02, ... in file order
  - every row id in "Rows covered" is a live PRD row
  - every Appendix A row of the milestone appears in a ticket of that file
  - no row appears in two tickets; no row sits in a file of a different
    milestone than Appendix A gives it
  - every dependency names a ticket that appears earlier in the same file or
    in an earlier milestone's file; no cycle
  - every acceptance criterion is a numbered item ending with a row-id list in
    parentheses, optionally followed by a full stop; every id it cites is in the ticket's rows; every covered row
    is cited by at least one criterion
  - no acceptance criterion carries a forbidden phrase ("as described in",
    "properly", "correctly", "etc.", "and so on", "appropriately",
    "as specified", "as required", "per the PRD", "according to")

--list   prints, per milestone, id, title, rows covered and depends on
--counts prints ticket and row counts per milestone
"""
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import prd_check  # noqa: E402

TICKETS_DIR = ROOT / "docs/design/tickets"
INDEX = ROOT / "docs/design/TICKETS.md"
MILESTONES = ROOT / "docs/design/milestones.md"
ORDER = ["A", "AB", "B"]

TICKET_RE = re.compile(r"^## (T-(A|AB|B)-(\d{2})): (.+?)\s*$")
META_RE = re.compile(r"^\|\s*([A-Za-z ]+?)\s*\|\s*(.*?)\s*\|\s*$")
SECTION_RE = re.compile(r"^### (.+?)\s*$")
ROW_ID_RE = re.compile(r"\bR-(?:T|I|H|O|F|S\d)-\d+\b")
TICKET_ID_RE = re.compile(r"\bT-(?:A|AB|B)-\d{2}\b")
CRIT_RE = re.compile(r"^(\d+)\.\s+(.*)$")
CRIT_END_RE = re.compile(r"\((R-[A-Z0-9]+-\d+(?:,\s*R-[A-Z0-9]+-\d+)*)\)\.?\s*$")
APPENDIX_RE = re.compile(
    r"^\| (R-[A-Z0-9]+-\d+) \| (Initial|Later) \| ([^|]+?) \| (A|AB|B|Later) \| ([^|]*?) \| (.*?) \|$",
    re.M,
)
FORBIDDEN = [
    "as described in", "properly", "correctly", "etc.", "and so on",
    "appropriately", "as specified", "as required", "per the prd", "according to",
]
META_KEYS = ["Milestone", "Blocks", "HLD components", "Depends on", "Rows covered"]
SECTIONS = ["Description", "Scope", "Acceptance criteria", "Verification"]


def appendix_map(errors):
    """Row id -> milestone from Appendix A of milestones.md."""
    if not MILESTONES.exists():
        errors.append(f"{MILESTONES.relative_to(ROOT)} not found")
        return {}
    out = {}
    for m in APPENDIX_RE.finditer(MILESTONES.read_text(encoding="utf-8")):
        rid, milestone = m.group(1), m.group(4)
        if rid in out and out[rid] != milestone:
            errors.append(f"milestones.md: {rid} mapped twice ({out[rid]} and {milestone})")
        out[rid] = milestone
    return out


def live_rows(errors):
    docs = prd_check.load_prd(errors)
    return set(prd_check.parse_rows(docs, errors))


def split_ids(cell):
    cell = cell.strip()
    if cell.lower() == "none" or not cell:
        return []
    return [c.strip() for c in cell.split(",") if c.strip()]


def parse_file(milestone, path, errors):
    """Return an ordered dict id -> ticket for one milestone file."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tickets = OrderedDict()
    current = None
    section = None
    for n, line in enumerate(lines, 1):
        m = TICKET_RE.match(line)
        if m:
            tid, ms, num, title = m.group(1), m.group(2), m.group(3), m.group(4)
            if tid in tickets:
                errors.append(f"{path.name}: {tid} appears twice")
            current = {"id": tid, "ms": ms, "num": int(num), "title": title, "line": n,
                       "meta": {}, "sections": OrderedDict(), "file": path.name}
            tickets[tid] = current
            section = None
            continue
        if current is None:
            continue
        s = SECTION_RE.match(line)
        if s:
            section = s.group(1)
            current["sections"][section] = []
            continue
        if section is None:
            mm = META_RE.match(line)
            if mm and mm.group(1) in META_KEYS:
                current["meta"][mm.group(1)] = mm.group(2)
        else:
            current["sections"][section].append(line)
    return tickets


def criteria_of(ticket):
    """Numbered acceptance criteria, continuation lines joined."""
    items = []
    for line in ticket["sections"].get("Acceptance criteria", []):
        m = CRIT_RE.match(line.strip())
        if m:
            items.append([int(m.group(1)), m.group(2)])
        elif items and line.strip():
            items[-1][1] += " " + line.strip()
    return items


def check_ticket(t, rows, errors):
    tid, name = t["id"], t["file"]
    for key in META_KEYS:
        if not t["meta"].get(key, "").strip():
            errors.append(f"{name} {tid}: missing or empty '{key}'")
    for sec in SECTIONS:
        body = "\n".join(t["sections"].get(sec, [])).strip()
        if not body:
            errors.append(f"{name} {tid}: empty or missing section '{sec}'")
    scope = "\n".join(t["sections"].get("Scope", []))
    for part in ("**In:**", "**Out:**"):
        idx = scope.find(part)
        if idx < 0 or not scope[idx + len(part):].strip().split("\n")[0].strip():
            errors.append(f"{name} {tid}: scope lacks a non-empty '{part}' line")
    if t["meta"].get("Milestone", "").strip() != t["ms"]:
        errors.append(f"{name} {tid}: milestone cell '{t['meta'].get('Milestone')}' does not match the id")
    covered = split_ids(t["meta"].get("Rows covered", ""))
    for rid in covered:
        if not ROW_ID_RE.fullmatch(rid):
            errors.append(f"{name} {tid}: '{rid}' is not a row id")
        elif rid not in rows:
            errors.append(f"{name} {tid}: {rid} is not a live PRD row")
    if len(set(covered)) != len(covered):
        errors.append(f"{name} {tid}: a row is listed twice in 'Rows covered'")
    cited = set()
    crits = criteria_of(t)
    if not crits:
        errors.append(f"{name} {tid}: no numbered acceptance criterion")
    for k, (num, body) in enumerate(crits, 1):
        if num != k:
            errors.append(f"{name} {tid}: acceptance criterion numbered {num}, expected {k}")
        m = CRIT_END_RE.search(body)
        if not m:
            errors.append(f"{name} {tid}: criterion {num} cites no row id at its end: '{body[:70]}'")
            continue
        for rid in split_ids(m.group(1)):
            cited.add(rid)
            if rid not in covered:
                errors.append(f"{name} {tid}: criterion {num} cites {rid}, which is not in 'Rows covered'")
        low = body.lower()
        for phrase in FORBIDDEN:
            if phrase in low:
                errors.append(f"{name} {tid}: criterion {num} contains '{phrase}'")
    for rid in covered:
        if rid not in cited:
            errors.append(f"{name} {tid}: {rid} is covered but no criterion cites it")
    return covered


def main(argv):
    errors = []
    rows = live_rows(errors)
    amap = appendix_map(errors)
    index_text = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    if not INDEX.exists():
        errors.append("docs/design/TICKETS.md not found")

    all_tickets = OrderedDict()
    per_file = OrderedDict()
    for ms in ORDER:
        path = TICKETS_DIR / f"{ms}.md"
        if not path.exists():
            continue
        if f"tickets/{ms}.md" not in index_text:
            errors.append(f"docs/design/TICKETS.md does not link tickets/{ms}.md")
        tickets = parse_file(ms, path, errors)
        if not tickets:
            errors.append(f"{path.name}: no ticket found")
        per_file[ms] = tickets
        for k, (tid, t) in enumerate(tickets.items(), 1):
            if t["ms"] != ms:
                errors.append(f"{path.name} {tid}: id names milestone {t['ms']} inside {ms}.md")
            if t["num"] != k:
                errors.append(f"{path.name} {tid}: numbered {t['num']:02d}, expected {k:02d} in file order")
            all_tickets[tid] = t

    seen_rows = {}
    for ms, tickets in per_file.items():
        for tid, t in tickets.items():
            covered = check_ticket(t, rows, errors)
            t["rows"] = covered
            for rid in covered:
                if rid in seen_rows:
                    errors.append(f"{t['file']} {tid}: {rid} is also covered by {seen_rows[rid]}")
                seen_rows[rid] = tid
                given = amap.get(rid)
                if given is None:
                    errors.append(f"{t['file']} {tid}: {rid} is not in Appendix A of milestones.md")
                elif given != ms:
                    errors.append(f"{t['file']} {tid}: {rid} sits at milestone {given} in Appendix A, not {ms}")
        expected = {rid for rid, m in amap.items() if m == ms}
        for rid in sorted(expected - set(seen_rows)):
            errors.append(f"{ms}.md: Appendix A row {rid} is in no ticket of milestone {ms}")

    # dependencies: earlier in the same file, or in an earlier milestone's file
    position = {tid: i for i, tid in enumerate(all_tickets)}
    deps = {}
    for tid, t in all_tickets.items():
        deps[tid] = split_ids(t["meta"].get("Depends on", ""))
        for d in deps[tid]:
            if not TICKET_ID_RE.fullmatch(d):
                errors.append(f"{t['file']} {tid}: dependency '{d}' is not a ticket id")
            elif d not in all_tickets:
                errors.append(f"{t['file']} {tid}: depends on {d}, which does not exist")
            elif d == tid:
                errors.append(f"{t['file']} {tid}: depends on itself")
            elif position[d] > position[tid]:
                errors.append(f"{t['file']} {tid}: depends on {d}, which appears later")
    # cycle detection (independent of the order check)
    state = {}

    def visit(tid, stack):
        if state.get(tid) == "done":
            return
        if state.get(tid) == "open":
            errors.append(f"dependency cycle: {' -> '.join(stack + [tid])}")
            return
        state[tid] = "open"
        for d in deps.get(tid, []):
            if d in all_tickets:
                visit(d, stack + [tid])
        state[tid] = "done"

    for tid in all_tickets:
        visit(tid, [])

    if "--list" in argv:
        for ms, tickets in per_file.items():
            print(f"\n## Milestone {ms}: {len(tickets)} tickets\n")
            print("| Id | Title | Rows covered | Depends on |")
            print("|---|---|---|---|")
            for tid, t in tickets.items():
                print(f"| {tid} | {t['title']} | {', '.join(t['rows'])} | {t['meta'].get('Depends on', '')} |")
    if "--counts" in argv:
        for ms, tickets in per_file.items():
            n = sum(len(t["rows"]) for t in tickets.values())
            print(f"{ms}: {len(tickets)} tickets, {n} rows")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"{len(errors)} problem(s)", file=sys.stderr)
        return 1
    total = sum(len(t) for t in per_file.values())
    print(f"ok: {total} tickets in {len(per_file)} file(s), rows placed once, order topological", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
