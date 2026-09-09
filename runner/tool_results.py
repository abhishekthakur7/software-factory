"""Tool-result shaping shared by the adapter's direct calls and the sandbox proxy's routed calls.

Deciding whether a raw result is small enough to hand back inline, and how
to excerpt it when it is not, is one rule bound to `limits.yaml`'s
`tool_result_inline` entry. The adapter's direct tool calls and the
proxy's relayed MCP-route calls each reach a result independently and on
their own thread; sharing this one function is what keeps the two paths
from ever disagreeing about where "small" ends for the same bytes.
"""
from dataclasses import dataclass

# Media types this rule treats as decodable text; anything else is opaque
# and is never returned inline or excerpted -- doing so would mean
# guessing a charset this function has no authority to assume.
_TEXT_PREFIX = "text/"
_TEXT_MEDIA_TYPES = frozenset({"application/json"})


@dataclass(frozen=True)
class Shaped:
    result_bytes: int
    inline: bool
    excerpt: str | None


def is_text(media_type: str) -> bool:
    return media_type.startswith(_TEXT_PREFIX) or media_type in _TEXT_MEDIA_TYPES


def _excerpt(lines: list[str], rule: dict) -> str:
    head = lines[: rule["excerpt_head_lines"]]
    tail = lines[-rule["excerpt_tail_lines"] :] if rule["excerpt_tail_lines"] else []
    max_bytes = rule["excerpt_max_bytes_per_end"]
    head_text = "\n".join(head).encode()[:max_bytes].decode(errors="ignore")
    tail_text = "\n".join(tail).encode()[:max_bytes].decode(errors="ignore")
    return f"{head_text}\n...\n{tail_text}"


def shape(result: bytes, *, media_type: str, rule: dict) -> Shaped:
    """The inline decision and excerpt for one raw result, against `rule` (`limits.yaml`'s `tool_result_inline`).

    Four cases, in order: a non-text result never decodes, so it is never
    inline and never carries an excerpt, regardless of size. A text result
    within `rule`'s line and byte bounds is inline, with the excerpt equal
    to its whole text -- it is already small enough to hand back as is. A
    larger text result with more than one line is excerpted head-and-tail.
    A larger text result of one line (or none) has no natural head/tail
    split, so it is stored but carries no excerpt.
    """
    result_bytes = len(result)
    if not is_text(media_type):
        return Shaped(result_bytes=result_bytes, inline=False, excerpt=None)

    text = result.decode(errors="ignore")
    lines = text.splitlines()
    inline = len(lines) <= rule["max_lines"] and result_bytes <= rule["max_bytes"]
    if inline:
        return Shaped(result_bytes=result_bytes, inline=True, excerpt=text)
    if len(lines) <= 1:
        return Shaped(result_bytes=result_bytes, inline=False, excerpt=None)
    return Shaped(result_bytes=result_bytes, inline=False, excerpt=_excerpt(lines, rule))
