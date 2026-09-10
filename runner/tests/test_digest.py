"""The digest records one utility run and one idempotent, minimal outbox intent."""
import json
import plistlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from runner import digest, outbox, owners, record, setup, trust_profile
from runner.db import connect
from runner.deliverers.slack import SlackDeliverer, SlackMCPPostTool, SlackMCPUnavailable
from runner.tests.fakes.slack_transport import FakeSlackPostTool
from runner.tests import test_outbox as outbox_harness


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
        assert digest.run(conn, channel=None, cadence="daily", now=datetime(2026, 1, 2, tzinfo=UTC), runs_dir=tmp_path, dispatch=False) is None
        assert conn.execute("SELECT COUNT(*) FROM external_write").fetchone()[0] == 0
        assert conn.execute("SELECT kind, outcome FROM utility_run").fetchone()["outcome"] == "pass"
    finally:
        conn.close()


def test_same_slot_and_item_list_reuses_the_one_digest_intent(tmp_path):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        now = datetime(2026, 1, 2, tzinfo=UTC)
        first = digest.run(conn, channel="C123", cadence="daily", now=now, runs_dir=tmp_path, dispatch=False)
        second = digest.run(conn, channel="C123", cadence="daily", now=now, runs_dir=tmp_path, dispatch=False)
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
        first = digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, 1, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        second = digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, 23, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        assert first == second
    finally:
        conn.close()


def test_reconciled_digest_slot_posts_once_through_the_guarded_slack_outbox(tmp_path, monkeypatch):
    conn = connect(tmp_path / "factory.sqlite")
    try:
        _seed(conn)
        post_tool = _live_slack(conn, tmp_path, monkeypatch)
        first = digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, 1, tzinfo=UTC), runs_dir=tmp_path)
        second = digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, 23, tzinfo=UTC), runs_dir=tmp_path)
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
        first = digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        assert record.get(conn, "external_write", first)["state"] == "pending"
        second = digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, 12, tzinfo=UTC), runs_dir=tmp_path)
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
        intent_id = digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
        record.update(conn, "external_write", intent_id, state="sending")
        conn.commit()
        outbox._reconcile_sending(
            conn, record.get(conn, "external_write", intent_id), runs_dir=tmp_path,
            profile_path=trust_profile.DEFAULT_TRUST_PROFILE_PATH, owners_path=owners.DEFAULT_OWNERS_PATH, now=None,
        )
        assert record.get(conn, "external_write", intent_id)["state"] == "sending"
        with pytest.raises(outbox.IntentRefused, match="still sending"):
            digest.run(conn, channel="C123", cadence="daily", now=datetime(2026, 1, 2, 12, tzinfo=UTC), runs_dir=tmp_path)
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
            digest.run(conn, channel=None, cadence="daily", now=datetime(2026, 1, 2, tzinfo=UTC), runs_dir=tmp_path, dispatch=False)
    finally:
        conn.close()


def test_scheduler_plist_uses_the_configured_cadence_and_channel(tmp_path):
    path = setup.write_digest_launchd_entry(
        {"digest": {"channel": "C123", "cadence": "weekly"}}, tmp_path, tmp_path / "factory", tmp_path / "factory.sqlite",
    )
    plist = path.read_text()
    assert path.name == "com.soft-factory.digest.plist"
    assert "C123" in plist
    assert "Weekday" in plist
    assert "digest" in plist


def test_scheduler_plist_escapes_paths_and_channels_without_changing_schedule(tmp_path):
    executable = tmp_path / "factory & digest"
    db_path = tmp_path / "runs & queue" / "factory.sqlite"
    document = plistlib.loads(setup.digest_launchd_plist({"digest": {"channel": "C&123", "cadence": "daily"}}, executable, db_path).encode())
    assert document["ProgramArguments"] == [str(executable), "--db", str(db_path), "digest"]
    assert document["EnvironmentVariables"] == {"FACTORY_DIGEST_CHANNEL": "C&123"}
    assert document["StartCalendarInterval"] == {"Hour": 9, "Minute": 0}


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
