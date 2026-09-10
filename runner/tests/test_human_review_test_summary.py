"""The packet/pr_body test summary: `packet_render`'s matching between the plan's `Test
strategy` table and the diff's test files.
"""
import sys

import pytest

from runner.paths import FACTORY_DIR

sys.path.insert(0, str(FACTORY_DIR / "scripts" / "tools"))
import packet_render  # noqa: E402


def test_a_diff_test_file_with_no_matching_strategy_row_is_unplanned():
    """A test file in the diff that no `Test strategy` row names is
    listed as "unplanned test, purpose not stated"."""
    rows = packet_render._test_summary_rows({
        "strategy_rows": [{"test": "WidgetUnitTest.java", "action": "change", "criteria": "AC-1", "proves": "the guard clause rejects negative input"}],
        "diff_test_files": ["src/test/java/com/fixture/NewHelperTest.java"],
    })
    assert rows == [{"test": "src/test/java/com/fixture/NewHelperTest.java", "criteria": "", "summary": "unplanned test, purpose not stated"}]


@pytest.mark.parametrize("action", ["change", "remove"])
def test_a_change_or_remove_strategy_row_is_summarised_against_the_criterion_it_names(action):
    """A `change` or `remove` `Test strategy` row is summarised in the
    test summary against the `AC-n` criterion (or task) its `criteria` cell names."""
    rows = packet_render._test_summary_rows({
        "strategy_rows": [{"test": "WidgetUnitTest.java", "action": action, "criteria": "AC-1", "proves": "the guard clause rejects negative input"}],
        "diff_test_files": ["src/test/java/com/fixture/WidgetUnitTest.java"],
    })
    assert rows == [{"test": "src/test/java/com/fixture/WidgetUnitTest.java", "criteria": "AC-1", "summary": "the guard clause rejects negative input"}]


def test_only_strategy_rows_whose_test_file_is_in_the_diff_produce_a_matched_row():
    """The test summary's matched rows correspond one-to-one with the
    diff's own test files -- a strategy row for a test the diff never touches contributes
    no row of its own."""
    rows = packet_render._test_summary_rows({
        "strategy_rows": [
            {"test": "WidgetUnitTest.java", "action": "change", "criteria": "AC-1", "proves": "the guard clause rejects negative input"},
            {"test": "UntouchedTest.java", "action": "change", "criteria": "AC-2", "proves": "never exercised by this diff"},
        ],
        "diff_test_files": ["src/test/java/com/fixture/WidgetUnitTest.java"],
    })
    assert len(rows) == 1
    assert rows[0]["test"] == "src/test/java/com/fixture/WidgetUnitTest.java"
    assert rows[0]["criteria"] == "AC-1"


def test_an_empty_diff_test_file_list_produces_no_rows():
    """A test summary with no test files touched in the diff renders no rows at all."""
    rows = packet_render._test_summary_rows({
        "strategy_rows": [{"test": "WidgetUnitTest.java", "action": "change", "criteria": "AC-1", "proves": "x"}],
        "diff_test_files": [],
    })
    assert rows == []


def test_a_none_size_strategy_row_names_no_diff_file_and_does_not_disturb_other_matches():
    """A `none`-size row names no automated test, so no diff file ever names it in turn -- it
    contributes no summary row of its own, and an ordinary row's match alongside it is unaffected."""
    rows = packet_render._test_summary_rows({
        "strategy_rows": [
            {"test": "WidgetUnitTest.java", "action": "change", "size": "small", "criteria": "AC-1", "proves": "the guard clause rejects negative input"},
            {"test": "none", "action": "add", "size": "none", "criteria": "AC-2", "proves": "the change only edits documentation"},
        ],
        "diff_test_files": ["src/test/java/com/fixture/WidgetUnitTest.java"],
    })
    assert rows == [{"test": "src/test/java/com/fixture/WidgetUnitTest.java", "criteria": "AC-1", "summary": "the guard clause rejects negative input"}]
