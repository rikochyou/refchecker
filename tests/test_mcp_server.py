from refchecker import mcp_server


def test_mcp_initialize_and_tools_list():
    init = mcp_server.handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18"},
    })
    assert init["result"]["serverInfo"]["name"] == "refchecker"
    assert init["result"]["capabilities"]["tools"] == {}

    tools = mcp_server.handle_message({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    })
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert {"check_reference_file", "check_reference_text", "test_reference_api_keys"} <= names


def test_mcp_check_reference_file_tool(tmp_path, monkeypatch):
    bib_path = tmp_path / "refs.bib"
    bib_path.write_text(
        """@article{demo,
  title = {A Tiny Test},
  author = {Lovelace, Ada},
  year = {1843}
}
""",
        encoding="utf-8",
    )

    def fake_verify_bib_file(path, **kwargs):
        output_dir = kwargs["output_dir"]
        return {
            "summary": {
                "total": 1,
                "found": 1,
                "not_found": 0,
                "needs_review": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 1,
                "output_dir": output_dir,
                "markdown_path": str(tmp_path / "out" / "report.md"),
                "csv_path": str(tmp_path / "out" / "result.csv"),
                "report_summary": "One item checked.",
            },
            "results": [
                {
                    "key": "demo",
                    "title": "A Tiny Test",
                    "status": "found",
                    "risk_level": "low",
                    "source": "FakeSource",
                    "suggested_action": "No action.",
                }
            ],
        }

    monkeypatch.setattr(mcp_server, "verify_bib_file", fake_verify_bib_file)
    response = mcp_server.handle_message({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "check_reference_file",
            "arguments": {
                "file_path": str(bib_path),
                "output_dir": str(tmp_path / "out"),
                "disabled_sources": ["url"],
            },
        },
    })

    assert response["result"]["isError"] is False
    text = response["result"]["content"][0]["text"]
    assert "RefChecker result for refs.bib" in text
    assert "One item checked." in text
    assert str(tmp_path / "out") in text
