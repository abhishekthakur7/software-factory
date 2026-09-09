"""Trusted-side Slack digest delivery through the official Slack MCP server's post tool."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Mapping

from runner import credentials, record
from runner.deliverers.stub import Receipt, RemoteRefused


class SlackMCPUnavailable(RemoteRefused):
    """No authenticated official Slack MCP post tool is bound to this trusted runner."""


class SlackMCPPostTool:
    """A Streamable-HTTP JSON-RPC client for one configured tool discovered from Slack's MCP server."""

    endpoint = "https://mcp.slack.com/mcp"

    def __init__(self, tool_name: str, argument_fields: Mapping[str, str], *, endpoint: str | None = None):
        if not tool_name or not all(argument_fields.get(name) for name in ("channel", "text")):
            raise SlackMCPUnavailable("digest MCP post tool is not configured")
        self._tool_name = tool_name
        self._argument_fields = dict(argument_fields)
        self._endpoint = endpoint or self.endpoint
        self._session_id: str | None = None

    @staticmethod
    def _decode_reply(raw: str) -> Mapping:
        lines = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        documents = lines if lines else [raw]
        for document in documents:
            try:
                parsed = json.loads(document)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, Mapping):
                return parsed
        raise SlackMCPUnavailable("Slack MCP server returned no JSON-RPC response")

    def _rpc(self, method: str, params: Mapping, credential: str, *, notification: bool = False) -> Mapping:
        body = {"jsonrpc": "2.0", "method": method, "params": dict(params)}
        if not notification:
            body["id"] = 1
        request = urllib.request.Request(
            self._endpoint, method="POST", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-03-26", **({"Mcp-Session-Id": self._session_id} if self._session_id else {})},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                self._session_id = response.headers.get("Mcp-Session-Id", self._session_id)
                raw = response.read().decode()
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise SlackMCPUnavailable("Slack MCP post-tool call failed") from exc
        if notification:
            return {}
        reply = self._decode_reply(raw)
        if "error" in reply:
            raise SlackMCPUnavailable("Slack MCP server refused the post-tool call")
        return reply.get("result") or {}

    @staticmethod
    def _message_identity(result: Mapping) -> str | None:
        structured = result.get("structuredContent")
        if isinstance(structured, Mapping):
            for key in ("ts", "message_ts", "message_id", "id"):
                if structured.get(key):
                    return str(structured[key])
        for item in result.get("content", []):
            if not isinstance(item, Mapping) or item.get("type") != "text":
                continue
            try:
                document = json.loads(item.get("text", ""))
            except json.JSONDecodeError:
                continue
            if isinstance(document, Mapping):
                for key in ("ts", "message_ts", "message_id", "id"):
                    if document.get(key):
                        return str(document[key])
        return None

    def __call__(self, arguments: Mapping, credential: str) -> Mapping:
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "soft-factory", "version": "0.1"}}, credential)
        self._rpc("notifications/initialized", {}, credential, notification=True)
        tools, cursor = [], None
        while True:
            page = self._rpc("tools/list", {} if cursor is None else {"cursor": cursor}, credential)
            tools.extend(page.get("tools", []))
            cursor = page.get("nextCursor")
            if not cursor:
                break
        tool = next((candidate for candidate in tools if candidate.get("name") == self._tool_name), None)
        schema = tool.get("inputSchema", {}) if isinstance(tool, Mapping) else {}
        properties = schema.get("properties", {}) if isinstance(schema, Mapping) else {}
        required = set(schema.get("required", [])) if isinstance(schema, Mapping) else set()
        selected = {self._argument_fields["channel"], self._argument_fields["text"]}
        if tool is None or not selected <= set(properties) or not selected <= required:
            raise SlackMCPUnavailable("configured Slack MCP tool does not accept its configured channel and text inputs")
        mapped = {self._argument_fields["channel"]: arguments["channel"], self._argument_fields["text"]: arguments["text"]}
        result = self._rpc("tools/call", {"name": self._tool_name, "arguments": mapped}, credential)
        if result.get("isError"):
            raise SlackMCPUnavailable("Slack MCP post tool returned an error")
        identity = self._message_identity(result)
        if identity is None:
            raise SlackMCPUnavailable("Slack MCP post tool returned no message identity")
        return {"ts": identity}


class SlackDeliverer:
    """Call the one injected official Slack MCP post tool with an already guarded digest projection."""

    def __init__(self, post_tool: Callable[[Mapping, str], Mapping] | None = None):
        self._post_tool = post_tool or self._unavailable

    @staticmethod
    def _unavailable(arguments: Mapping, credential: str) -> Mapping:
        raise SlackMCPUnavailable("the trusted runner has no authenticated Slack MCP post-tool binding")

    def receipt_for_key(self, key: str) -> Receipt | None:
        return None

    def digest(self, intent: Mapping, payload: Mapping) -> Receipt:
        channel = intent["digest_channel"]
        if not isinstance(channel, str) or not channel:
            raise RemoteRefused("digest intent has no configured channel")
        items = payload.get("items")
        if not isinstance(items, list):
            raise RemoteRefused("guarded digest has no item list")
        text = "\n".join(
            f"{item['ticket_id']} | {item['tier']} | {item['item_kind']} | {item['age']} | {item['command']}"
            for item in items
        )
        result = self._post_tool({"channel": channel, "text": text}, credentials.fetch(credentials.SLACK_DIGEST_ROLE))
        identity = result.get("ts")
        if not identity:
            raise SlackMCPUnavailable("Slack MCP post tool returned no message identity")
        return Receipt(
            remote_identity=f"slack:{channel}:{identity}", remote_pr_identity=None, remote_head_sha=None, body_hash=None,
            payload_digest=intent["payload_digest"], idempotency_key=intent["idempotency_key"], created_at=record.now(),
        )
