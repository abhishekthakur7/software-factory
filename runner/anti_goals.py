"""The anti-goals of charter section 3, the other half of the R-F-11 fence.

Kept as code, not markdown, so criterion 11's manifest walk can name this
module directly. See `state_table.py` for why both stay outside `factory/`.
"""

ANTI_GOALS: tuple[tuple[str, str], ...] = (
    ("no_autonomous_merge_or_deploy", "No autonomous merge or deploy."),
    ("no_replacing_human_review", "No replacing human review."),
    ("no_throughput_optimization", "No throughput optimization."),
    ("no_self_grading_judge", "No self-grading judge."),
    ("no_measure_feeds_performance_review", "No measure feeds performance review."),
    ("no_greenfield_mode", "No greenfield mode."),
    ("no_generic_product", "No generic product."),
    ("no_black_box", "No black box."),
    ("no_unisolated_implementation", "No unisolated implementation."),
    ("no_unapproved_data_boundary", "No unapproved data boundary."),
    ("no_stale_approval", "No stale approval."),
)
