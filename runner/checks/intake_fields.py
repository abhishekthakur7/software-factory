"""The intake field gate: acceptance criteria, owner, parent/Confluence link, and issue type.

`check` is a pure function over a payload and a field-name mapping: it
never reads a file or a connection itself, so the same logic runs over a
freshly read Jira issue's raw fields and, for a ticket that already
carries a `ticket_source` artefact, over that artefact's own front-matter
keys -- the caller supplies whichever `field_names` mapping matches the
payload's shape. Every reason is checked in a fixed order and the first
hit wins, since a ticket missing several fields at once still gets one
clear reason to act on rather than a list.
"""
from dataclasses import dataclass

CHECK_NAME = "intake_fields"

# The logical fields a valid intake needs, and the order their absence is
# checked in -- acceptance criteria first, since it is the field every
# other stage's brief and plan ultimately trace back to.
_LOGICAL_FIELDS = ("acceptance_criteria", "owner", "parent_link", "confluence_link", "issue_type")


@dataclass(frozen=True)
class Finding:
    check_name: str
    result: str  # "pass" | "fail"
    detail: str


def _blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def check(payload: dict, *, field_names: dict) -> Finding:
    """Whether `payload` clears the four intake requirements, reading each field by `field_names`'s logical-to-actual mapping.

    `field_names` must carry every name in `_LOGICAL_FIELDS`; a payload
    missing several of them still yields exactly one `Finding`, naming
    the first hit in this order: empty or missing acceptance criteria,
    no named owner, neither a parent link nor a Confluence link, and
    issue type `Epic` (which needs child tickets rather than a direct
    ticket).
    """
    payload = payload or {}
    if _blank(payload.get(field_names["acceptance_criteria"])):
        return Finding(CHECK_NAME, "fail", "missing acceptance criteria")
    if _blank(payload.get(field_names["owner"])):
        return Finding(CHECK_NAME, "fail", "missing owner")
    parent_link = payload.get(field_names["parent_link"])
    confluence_link = payload.get(field_names["confluence_link"])
    if _blank(parent_link) and _blank(confluence_link):
        return Finding(CHECK_NAME, "fail", "missing parent or Confluence link")
    if payload.get(field_names["issue_type"]) == "Epic":
        return Finding(CHECK_NAME, "fail", "needs child tickets")
    return Finding(CHECK_NAME, "pass", "acceptance criteria, owner, a parent or Confluence link, and issue type all present")
