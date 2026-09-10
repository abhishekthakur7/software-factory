"""The digest records one utility run and one idempotent, minimal outbox intent."""
import json
import os
import plistlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from runner import credentials, digest, outbox, owners, project, record, setup, trust_profile
from runner.db import connect
from runner.deliverers.slack import SlackDeliverer, SlackMCPPostTool, SlackMCPUnavailable
from runner.tests.fakes.slack_transport import FakeSlackPostTool
from runner.tests import test_outbox as outbox_harness


SCHEDULE = digest.Schedule.from_config(None, zone=UTC)


def _seed(conn):
    ticket_id = record.insert(conn, "ticket", state="context", opened_at=record.now())
    record.insert(conn, "queue_item", ticket_id=ticket_id, tier="standard", kind="red_check", ref="check_result:1", queued_at="2026-01-01T00:00:00+00:00")


def _live_slack(conn, tmp_path, monkeypatch):
    outbox_harness._activate(conn, trust_profile.DEFAULT_TRUST_PROFILE_PATH, owners.DEFAULT_OWNERS_PATH)
    post_tool = FakeSlackPostTool()
    route = trust_profile.load_trust_profile().routes["slack_digest"]
    monkeypatch.setattr(outbox, "_route_and_deliverer", lambda *args, **kwargs: (route, SlackDeliverer(post_tool)))
    monkeypatch.setattr("runner.deliverers.slack.credentials.fetch", lambda role: "credential")
    return post_tool


def test_empty_queue_records_a_digest_run_without_an_external_write(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        assert digest.run(conn, channel=None, schedule=SCHEDULE, now=datetime(2026, 1, 2, 10, 5, tzinfo=UTC), runs_dir=tmp_path, dispatch=False) is None
        assert conn.execute("SELECT COUNT(*) FROM external_write").fetchone()[0] == 0
        assert conn.execute("SELECT kind, outcome FROM utility_run").fetchone()["outcome"] == "pass"
    finally:
        conn.close()


def test_same_slot_and_item_list_reuses_the_one_digest_intent(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        now = datetime(2026, 1, 2, 10, 5, tzinfo=UTC)
        first = digest.run(conn, channel="C123", schedule=SCHEDULE, now=now, runs_dir=tmp_path, dispatch=False)
        second = digest.run(conn, channel="C123", schedule=SCHEDULE, now=now, runs_dir=tmp_path, dispatch=False)
        assert first == second
        assert conn.execute("SELECT COUNT(*) FROM external_write").fetchone()[0] == 1
        payload = conn.execute("SELECT path FROM artefact WHERE kind = 'outbox_payload'").fetchone()["path"]
        assert '"channel":"C123"' in open(payload).read()
    finally:
        conn.close()


def test_item_age_is_snapshotted_at_the_slot_boundary_for_idempotency(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        first = digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 10, 5, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        second = digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 14, 59, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        assert first == second
    finally:
        conn.close()


def test_reconciled_digest_slot_posts_once_through_the_guarded_slack_outbox(tmp_path, monkeypatch):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        post_tool = _live_slack(conn, tmp_path, monkeypatch)
        first = digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 10, 5, tzinfo=UTC), runs_dir=tmp_path)
        second = digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 14, 59, tzinfo=UTC), runs_dir=tmp_path)
        assert first == second
        assert len(post_tool.calls) == 1
        assert record.get(conn, "external_write", first)["state"] == "reconciled"
        utility_rows = conn.execute("SELECT kind, outcome, outputs FROM utility_run ORDER BY id").fetchall()
        assert [(row["kind"], row["outcome"]) for row in utility_rows] == [("digest", "pass"), ("digest", "pass")]
        assert [json.loads(row["outputs"])["intent_id"] for row in utility_rows] == [first, first]
        assert conn.execute("SELECT COUNT(*) FROM artefact WHERE kind = 'receipt'").fetchone()[0] == 1
    finally:
        conn.close()


def test_pending_digest_slot_dispatches_once_when_a_retry_reaches_send(tmp_path, monkeypatch):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        post_tool = _live_slack(conn, tmp_path, monkeypatch)
        first = digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 10, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        assert record.get(conn, "external_write", first)["state"] == "pending"
        second = digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 12, tzinfo=UTC), runs_dir=tmp_path)
        assert first == second
        assert record.get(conn, "external_write", first)["state"] == "reconciled"
        assert len(post_tool.calls) == 1
    finally:
        conn.close()


def test_must_retain_an_ambiguous_sending_digest_without_another_slack_post(tmp_path, monkeypatch):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        post_tool = _live_slack(conn, tmp_path, monkeypatch)
        intent_id = digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 10, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        record.update(conn, "external_write", intent_id, state="sending")
        conn.commit()
        outbox._reconcile_sending(
            conn, record.get(conn, "external_write", intent_id), runs_dir=tmp_path,
            profile_path=trust_profile.DEFAULT_TRUST_PROFILE_PATH, owners_path=owners.DEFAULT_OWNERS_PATH, now=None,
        )
        assert record.get(conn, "external_write", intent_id)["state"] == "sending"
        with pytest.raises(outbox.IntentRefused, match="still sending"):
            digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(2026, 1, 2, 12, tzinfo=UTC), runs_dir=tmp_path)
        assert post_tool.calls == []
    finally:
        conn.close()


def test_slack_delivery_uses_the_intent_channel_and_only_the_guarded_item_fields(monkeypatch):
    post_tool = FakeSlackPostTool()
    monkeypatch.setattr("runner.deliverers.slack.credentials.fetch", lambda role: "credential")
    receipt = SlackDeliverer(post_tool).digest(
        {"digest_channel": "C-bound", "payload_digest": "digest", "idempotency_key": "key"},
        {"items": [{"ticket_id": "AB-1", "tier": "standard", "item_kind": "review", "age": "1h", "command": "factory act 1 inspect --actor <identity>"}]},
    )
    assert post_tool.calls == [({"channel": "C-bound", "text": "AB-1 | standard | review | 1h | factory act 1 inspect --actor <identity>"}, "credential")]
    assert receipt.remote_identity == "slack:C-bound:123.456"


def test_slack_mcp_initializes_parses_sse_and_uses_the_configured_argument_mapping(monkeypatch):
    requests = []
    replies = iter([
        '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26"}}',
        '',
        'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"post_digest","inputSchema":{"properties":{"channel_id":{},"markdown":{}},"required":["channel_id","markdown"]}}]}}\n\n',
        '{"jsonrpc":"2.0","id":1,"result":{"structuredContent":{"message_ts":"123.456"}}}',
    ])

    class Response:
        headers = {"Mcp-Session-Id": "session"}
        def read(self): return next(replies).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return False

    def fake_urlopen(request, timeout):
        requests.append(request)
        return Response()

    monkeypatch.setattr("runner.deliverers.slack.urllib.request.urlopen", fake_urlopen)
    tool = SlackMCPPostTool("post_digest", {"channel": "channel_id", "text": "markdown"})
    assert tool({"channel": "C1", "text": "digest"}, "credential") == {"ts": "123.456"}
    methods = [__import__("json").loads(request.data)["method"] for request in requests]
    assert methods == ["initialize", "notifications/initialized", "tools/list", "tools/call"]
    assert __import__("json").loads(requests[-1].data)["params"]["arguments"] == {"channel_id": "C1", "markdown": "digest"}
    assert all(request.headers["Mcp-protocol-version"] == "2025-03-26" for request in requests)


def test_must_reject_slack_mcp_tool_error_before_a_receipt(monkeypatch):
    replies = iter([
        '{"jsonrpc":"2.0","id":1,"result":{}}', '',
        '{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"post_digest","inputSchema":{"properties":{"channel":{},"text":{}},"required":["channel","text"]}}]}}',
        '{"jsonrpc":"2.0","id":1,"result":{"isError":true,"content":[{"type":"text","text":"denied"}]}}',
    ])
    class Response:
        headers = {}
        def read(self): return next(replies).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr("runner.deliverers.slack.urllib.request.urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(SlackMCPUnavailable, match="error"):
        SlackMCPPostTool("post_digest", {"channel": "channel", "text": "text"})({"channel": "C1", "text": "digest"}, "credential")


def test_must_reject_populated_queue_without_a_configured_channel(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        with pytest.raises(digest.DigestConfigurationError, match="channel"):
            digest.run(conn, channel=None, schedule=SCHEDULE, now=datetime(2026, 1, 2, 10, 5, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
    finally:
        conn.close()


def test_scheduler_plist_carries_one_entry_per_scheduled_weekday_and_time(tmp_path):
    """the default schedule runs the digest twice a day from Monday to
    Friday, and the scheduler entry names all ten occurrences."""
    path = setup.write_digest_launchd_entry(
        {"digest": {"channel": "C123"}}, tmp_path, tmp_path / "factory", tmp_path / "factory.sqlite",
    )
    document = plistlib.loads(path.read_bytes())
    assert path.name == "com.soft-factory.digest.plist"
    assert document["EnvironmentVariables"] == {"FACTORY_DIGEST_CHANNEL": "C123"}
    assert document["ProgramArguments"][-1] == "digest"
    assert document["StartCalendarInterval"] == [
        {"Weekday": weekday, "Hour": hour, "Minute": 0} for weekday in range(1, 6) for hour in (10, 15)
    ]


def test_scheduler_plist_escapes_paths_and_channels_without_changing_schedule(tmp_path):
    """a configured weekday is written in launchd's own numbering, which
    counts Sunday as zero, whatever the paths and channel contain."""
    executable = tmp_path / "factory & digest"
    db_path = tmp_path / "runs & queue" / "factory.sqlite"
    document = plistlib.loads(setup.digest_launchd_plist(
        {"digest": {"channel": "C&123", "times": ["07:30"], "weekdays": ["sunday"]}}, executable, db_path,
    ).encode())
    assert document["ProgramArguments"] == [str(executable), "--db", str(db_path), "digest"]
    assert document["EnvironmentVariables"] == {"FACTORY_DIGEST_CHANNEL": "C&123"}
    assert document["StartCalendarInterval"] == [{"Weekday": 0, "Hour": 7, "Minute": 30}]


def test_must_reject_a_scheduler_entry_whose_schedule_names_no_time(tmp_path):
    with pytest.raises(setup.SetupError, match="times"):
        setup.digest_launchd_plist(
            {"digest": {"channel": "C123", "times": []}}, tmp_path / "factory", tmp_path / "factory.sqlite",
        )


def test_each_scheduled_occurrence_earns_its_own_digest_intent(tmp_path):
    """two runs inside one occurrence serve the same slot, while the day's
    later occurrence and the same time on the next working day are separate
    slots; a weekend run still serves the last working day's occurrence."""
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        def at(*when):
            return digest.run(conn, channel="C123", schedule=SCHEDULE, now=datetime(*when, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)

        morning, morning_again = at(2026, 1, 2, 10, 5), at(2026, 1, 2, 14, 59)
        afternoon, weekend = at(2026, 1, 2, 15, 5), at(2026, 1, 4, 12)
        next_working_day = at(2026, 1, 5, 10, 5)
        assert morning == morning_again
        assert weekend == afternoon
        assert len({morning, afternoon, next_working_day}) == 3
        slots = [row["schedule_slot"] for row in conn.execute("SELECT schedule_slot FROM external_write ORDER BY id")]
        assert slots == ["2026-01-02T10:00", "2026-01-02T15:00", "2026-01-05T10:00"]
    finally:
        conn.close()


def test_must_reject_a_schedule_that_names_no_times():
    with pytest.raises(digest.DigestConfigurationError, match="times"):
        digest.Schedule.from_config({"times": [], "weekdays": ["monday"]})


def test_must_reject_a_time_that_is_not_a_time_of_day():
    with pytest.raises(digest.DigestConfigurationError, match="HH:MM"):
        digest.Schedule.from_config({"times": ["10 a.m."], "weekdays": ["monday"]})


def test_must_reject_a_weekday_that_is_not_a_named_day():
    """weekdays are named, never numbered, because every numbering in reach
    starts the week on a different day."""
    with pytest.raises(digest.DigestConfigurationError, match="weekday"):
        digest.Schedule.from_config({"times": ["10:00"], "weekdays": [1]})


@pytest.mark.skipif(
    not os.environ.get("SOFT_FACTORY_DIGEST_CHANNEL"),
    reason="SOFT_FACTORY_DIGEST_CHANNEL names no channel: the closing run needs a real Slack workspace to post into",
)
def test_closing_run_posts_once_to_the_real_slack_channel(tmp_path):
    """the closing run posts the digest once to the configured Slack
    channel, through the real Slack MCP server and the real deliverer, and
    leaves exactly one dispatched external write behind.

    Skipped loudly wherever the real Slack workspace is out of reach --
    no channel named for this host, no `slack_digest` Keychain item, or
    no post-tool binding chosen yet in `project.yaml`."""
    if not credentials.available(credentials.SLACK_DIGEST_ROLE):
        pytest.skip("no slack_digest Keychain item on this host: the real Slack MCP server cannot be authenticated")
    settings = project.load().get("digest") or {}
    if not (settings.get("channel") and settings.get("mcp_post_tool")):
        pytest.skip("project.yaml carries no Slack channel and MCP post-tool binding: the owner chooses both after Slack app approval")

    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        outbox_harness._activate(conn, trust_profile.DEFAULT_TRUST_PROFILE_PATH, owners.DEFAULT_OWNERS_PATH)
        intent_id = digest.run(
            conn, channel=os.environ["SOFT_FACTORY_DIGEST_CHANNEL"],
            schedule=digest.Schedule.from_config(settings), runs_dir=tmp_path,
        )
        assert conn.execute("SELECT COUNT(*) FROM external_write").fetchone()[0] == 1
        assert record.get(conn, "external_write", intent_id)["state"] == "reconciled"
    finally:
        conn.close()


def test_digest_tool_runs_an_empty_database_as_a_subprocess(tmp_path):
    db_path = tmp_path / "factory.sqlite"
    script = Path(__file__).parents[2] / "factory" / "scripts" / "tools" / "digest"
    result = subprocess.run([sys.executable, str(script), "--db", str(db_path)], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "digest: no open items"
    conn = connect(db_path)
    try:
        assert conn.execute("SELECT kind, outcome FROM utility_run").fetchone()["kind"] == "digest"
    finally:
        conn.close()
