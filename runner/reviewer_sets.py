"""Reviewer slots: the canonical requirement a gate must see approved.

A slot is keyed by role, owner and source rule; that key, rendered as
`slot_id`, is what an `approval_record` names and what another slot's
`distinct_from` constraint points at. `merge_slots` builds the effective
set from a planned and an actual set: two slots sharing one key collapse to
the larger minimum count and the union of their separation constraints,
and every slot present on only one side is kept, so a path dropped from the
plan never silently drops the reviewer the plan promised. Derivation of the
actual set from a diff and CODEOWNERS lives beside this in the same module;
the slot model and the merge come first because approval quorum and
evidence tuples read slots without ever deriving one.
"""
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Slot:
    """One requirement slot. `role` xor `owner` is the canonical reviewer; both may be set when a role resolves to a person."""

    source_rule: str
    role: str | None = None
    owner: str | None = None
    matched_path: str | None = None
    pattern: str | None = None
    precedence: int | None = None
    min_count: int = 1
    # slot_ids whose satisfying actors must differ from this slot's actors.
    distinct_from: tuple[str, ...] = ()
    # False marks a new or unresolved owner: the slot blocks the gate.
    resolved: bool = True

    @property
    def key(self) -> tuple[str | None, str | None, str]:
        return (self.role, self.owner, self.source_rule)

    @property
    def slot_id(self) -> str:
        return "|".join(part or "" for part in self.key)

    def to_json(self) -> dict:
        return {**asdict(self), "slot_id": self.slot_id, "distinct_from": list(self.distinct_from)}

    @classmethod
    def from_json(cls, data: dict) -> "Slot":
        fields = {name: data[name] for name in cls.__dataclass_fields__ if name in data}
        fields["distinct_from"] = tuple(fields.get("distinct_from", ()))
        return cls(**fields)


def merge_slots(planned: list[Slot], actual: list[Slot]) -> list[Slot]:
    """The effective set: matching keys merge, everything else is preserved, order is planned-first then new actual keys."""
    merged: dict[tuple, Slot] = {slot.key: slot for slot in planned}
    for slot in actual:
        prior = merged.get(slot.key)
        if prior is None:
            merged[slot.key] = slot
            continue
        merged[slot.key] = Slot(
            source_rule=slot.source_rule,
            role=slot.role,
            owner=slot.owner,
            matched_path=slot.matched_path or prior.matched_path,
            pattern=slot.pattern or prior.pattern,
            precedence=slot.precedence if slot.precedence is not None else prior.precedence,
            min_count=max(prior.min_count, slot.min_count),
            distinct_from=tuple(sorted(set(prior.distinct_from) | set(slot.distinct_from))),
            resolved=prior.resolved and slot.resolved,
        )
    return list(merged.values())
