"""Minimal MCP stdio client (JSON-RPC + Content-Length framing)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class McpServerSpec:
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class McpTool:
    server: str
    name: str
    description: str
    input_schema: Dict[str, Any]


class McpStdioSession:
    def __init__(self, spec: McpServerSpec) -> None:
        self.spec = spec
        env = os.environ.copy()
        env.update(spec.env)
        self.proc = subprocess.Popen(
            [spec.command, *spec.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        self._id = 0
        self._lock = threading.Lock()
        self._initialize()

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                self.proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            try:
                self.proc.kill()
            except Exception:  # noqa: BLE001
                pass

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _write(self, message: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        raw = json.dumps(message, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
        self.proc.stdin.write(header + raw)
        self.proc.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        assert self.proc.stdout is not None
        # headers
        content_length = None
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError(f"MCP server {self.spec.name} closed stdout")
            if line in (b"\r\n", b"\n"):
                break
            if line.lower().startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1].strip())
        if content_length is None:
            raise RuntimeError(f"MCP {self.spec.name}: missing Content-Length")
        body = self.proc.stdout.read(content_length)
        return json.loads(body.decode("utf-8"))

    def request(self, method: str, params: Optional[dict[str, Any]] = None) -> Any:
        with self._lock:
            msg = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
                "params": params or {},
            }
            self._write(msg)
            while True:
                resp = self._read_message()
                # skip notifications
                if "id" not in resp:
                    continue
                if "error" in resp:
                    err = resp["error"]
                    raise RuntimeError(
                        f"MCP {self.spec.name} {method}: {err.get('message') or err}"
                    )
                return resp.get("result")

    def notify(self, method: str, params: Optional[dict[str, Any]] = None) -> None:
        with self._lock:
            self._write(
                {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or {},
                }
            )

    def _initialize(self) -> None:
        result = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "xp", "version": "0.6.0"},
            },
        )
        self.notify("notifications/initialized", {})
        _ = result

    def list_tools(self) -> List[McpTool]:
        result = self.request("tools/list", {})
        tools = []
        for t in result.get("tools") or []:
            tools.append(
                McpTool(
                    server=self.spec.name,
                    name=t.get("name") or "",
                    description=t.get("description") or "",
                    input_schema=t.get("inputSchema")
                    or {"type": "object", "properties": {}},
                )
            )
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        # content can be list of {type,text}
        content = result.get("content") if isinstance(result, dict) else result
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text") or "")
                    else:
                        parts.append(json.dumps(block, ensure_ascii=False))
                else:
                    parts.append(str(block))
            text = "\n".join(parts)
        else:
            text = json.dumps(result, ensure_ascii=False)
        if isinstance(result, dict) and result.get("isError"):
            return f"error: MCP tool failed\n{text}"
        return text or "(empty MCP result)"


class McpRegistry:
    """Owns multiple MCP sessions and exposes OpenAI-style tool defs."""

    def __init__(self) -> None:
        self.sessions: Dict[str, McpStdioSession] = {}
        self.tools: List[McpTool] = []
        # qualified name mcp__server__tool -> (server, tool)
        self._map: Dict[str, tuple[str, str]] = {}

    def connect(self, specs: List[McpServerSpec]) -> List[str]:
        errors: List[str] = []
        for spec in specs:
            try:
                sess = McpStdioSession(spec)
                listed = sess.list_tools()
                self.sessions[spec.name] = sess
                for t in listed:
                    qname = f"mcp__{spec.name}__{t.name}"
                    # sanitize for providers that dislike dots
                    qname = qname.replace(".", "_").replace("-", "_")
                    self._map[qname] = (spec.name, t.name)
                    self.tools.append(
                        McpTool(
                            server=t.server,
                            name=qname,
                            description=f"[MCP:{spec.name}] {t.description}",
                            input_schema=t.input_schema,
                        )
                    )
            except Exception as e:  # noqa: BLE001
                errors.append(f"{spec.name}: {e}")
        return errors

    def tool_defs(self) -> List[dict[str, Any]]:
        defs = []
        for t in self.tools:
            defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema
                        or {"type": "object", "properties": {}},
                    },
                }
            )
        return defs

    def call(self, qualified_name: str, arguments: dict[str, Any] | str) -> str:
        if qualified_name not in self._map:
            return f"error: unknown MCP tool {qualified_name}"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments else {}
            except json.JSONDecodeError:
                return f"error: invalid JSON arguments for {qualified_name}"
        server, tool = self._map[qualified_name]
        sess = self.sessions.get(server)
        if not sess:
            return f"error: MCP server not connected: {server}"
        try:
            return sess.call_tool(tool, arguments)
        except Exception as e:  # noqa: BLE001
            return f"error: MCP call failed: {type(e).__name__}: {e}"

    def close(self) -> None:
        for s in self.sessions.values():
            s.close()
        self.sessions.clear()


def parse_mcp_config(data: dict[str, Any]) -> List[McpServerSpec]:
    """
    Accept:
      [[mcp_servers]]
      name = "filesystem"
      command = "npx"
      args = ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    or:
      [mcp_servers.filesystem]
      command = "..."
      args = [...]
    """
    specs: List[McpServerSpec] = []
    raw = data.get("mcp_servers")
    if raw is None:
        return specs
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "mcp")
            cmd = str(item.get("command") or "")
            if not cmd:
                continue
            args = [str(a) for a in (item.get("args") or [])]
            env = {str(k): str(v) for k, v in (item.get("env") or {}).items()}
            specs.append(McpServerSpec(name=name, command=cmd, args=args, env=env))
    elif isinstance(raw, dict):
        for name, item in raw.items():
            if not isinstance(item, dict):
                continue
            cmd = str(item.get("command") or "")
            if not cmd:
                continue
            args = [str(a) for a in (item.get("args") or [])]
            env = {str(k): str(v) for k, v in (item.get("env") or {}).items()}
            specs.append(McpServerSpec(name=str(name), command=cmd, args=args, env=env))
    return specs
