from __future__ import annotations

from xp.mcp_client import parse_mcp_config


def test_parse_list_form():
    data = {
        "mcp_servers": [
            {
                "name": "fs",
                "command": "npx",
                "args": ["-y", "pkg", "/tmp"],
                "env": {"A": "1"},
            }
        ]
    }
    specs = parse_mcp_config(data)
    assert len(specs) == 1
    assert specs[0].name == "fs"
    assert specs[0].command == "npx"
    assert specs[0].args[0] == "-y"
    assert specs[0].env["A"] == "1"


def test_parse_table_form():
    data = {
        "mcp_servers": {
            "memory": {"command": "uvx", "args": ["mcp-server-memory"]},
        }
    }
    specs = parse_mcp_config(data)
    assert len(specs) == 1
    assert specs[0].name == "memory"
    assert specs[0].command == "uvx"
