"""Reviewer sets: the slot model and the planned/actual merge into the effective set."""
from runner.reviewer_sets import Slot, merge_slots


def test_slot_id_is_the_canonical_key_of_role_owner_and_source_rule():
    slot = Slot(source_rule="CODEOWNERS:3", owner="alice", matched_path="src/a.java", pattern="src/**")
    assert slot.slot_id == "|alice|CODEOWNERS:3"
    assert Slot.from_json(slot.to_json()) == slot


def test_matching_planned_and_actual_slots_merge_to_max_count_and_union_of_separation():
    planned = Slot(source_rule="CODEOWNERS:3", owner="alice", min_count=1, distinct_from=("x",))
    actual = Slot(source_rule="CODEOWNERS:3", owner="alice", min_count=2, distinct_from=("y",), matched_path="src/a.java")
    [merged] = merge_slots([planned], [actual])
    assert merged.key == planned.key
    assert merged.min_count == 2
    assert merged.distinct_from == ("x", "y")
    assert merged.matched_path == "src/a.java"


def test_removing_a_planned_path_never_removes_its_slot_and_a_nonmatching_slot_is_preserved():
    """the planned slot for a path the actual diff no longer touches stays in
    the effective set, and a slot only the actual diff produced is added."""
    planned_only = Slot(source_rule="CODEOWNERS:7", owner="bob", matched_path="src/b.java")
    actual_only = Slot(source_rule="CODEOWNERS:9", role="sensitive_path_owner", matched_path="src/auth/c.java")
    effective = merge_slots([planned_only], [actual_only])
    assert [slot.key for slot in effective] == [planned_only.key, actual_only.key]


def test_merged_slot_is_unresolved_when_either_side_is():
    planned = Slot(source_rule="CODEOWNERS:3", owner="alice")
    actual = Slot(source_rule="CODEOWNERS:3", owner="alice", resolved=False)
    [merged] = merge_slots([planned], [actual])
    assert merged.resolved is False
