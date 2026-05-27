import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from refchecker import batch, cli, mcp_server


def test_verify_text_writes_reports_and_citation_consistency(tmp_path, monkeypatch):
    def fake_verify_entry(
        title,
        author,
        year,
        doi,
        threshold,
        email,
        use_openalex,
        use_dblp,
        **kwargs,
    ):
        return {
            "found": True,
            "status": "found",
            "matched_title": title,
            "similarity": 1.0,
            "source": "FakeSource",
            "venue": "Fake Journal",
            "type": "article",
            "authors": "Ada Lovelace",
            "author_list": [],
            "year": year,
            "doi": doi,
            "url": "",
            "reason": "",
            "author_check": "unknown",
            "author_reason": "not checked in fake",
            "year_check": "exact",
            "year_reason": "year ok",
            "bib_year": year,
            "matched_year": year,
            "doi_check": "exact" if doi else "unknown",
            "doi_reason": "",
            "bib_doi": doi,
            "matched_doi": doi,
            "needs_review": "No",
            "review_reasons": "",
            "search_mode": kwargs.get("search_mode", "strict"),
            "source_order": "CrossRef",
            "actual_query_trace": "CrossRef: found (100%)",
            "adopted_source": "FakeSource",
            "doi_check_status": "not_provided",
            "candidate_count": 1,
            "alternative_candidates": "",
            "candidate_conflict": "No",
            "arbitration_reason": "fake arbitration",
        }

    monkeypatch.setattr(batch._verifier, "verify_entry", fake_verify_entry)
    text = (
        "Lovelace (1843) is cited, but Turing (1950) is missing.\n\n"
        "References\n\n"
        "Lovelace, A. (1843). Notes on the analytical engine. Journal. "
        "https://doi.org/10.1000/love\n\n"
        "Hopper, G. (1952). The education of a computer. Journal."
    )

    result = batch.verify_text(
        text,
        output_dir=str(tmp_path),
        use_openalex=False,
        use_dblp=False,
        use_semantic_scholar=False,
        use_arxiv=False,
        use_pubmed=False,
        use_url_verify=False,
        delay=0,
        human_output=False,
    )

    summary = result["summary"]
    assert summary["total"] == 2
    assert summary["found"] == 2
    assert summary["missing_reference_citations"] == 1
    assert summary["uncited_references"] == 1
    assert Path(summary["markdown_path"]).exists()
    assert Path(summary["csv_path"]).exists()
    citation_path = Path(summary["citation_consistency_path"])
    assert citation_path.exists()
    citation = json.loads(citation_path.read_text(encoding="utf-8"))
    assert citation["missing_references"][0]["signature"] == "turing:1950"


def test_cli_test_api_keys_without_file(monkeypatch):
    captured = {}

    def fake_test_api_keys(**kwargs):
        captured.update(kwargs)
        return {"results": [], "summary": {"total": 0}}

    monkeypatch.setattr(cli, "test_api_keys", fake_test_api_keys)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refchecker",
            "--test-api-keys",
            "--sources",
            "springer",
            "--springer-api-key",
            "secret",
            "--jsonl-progress",
        ],
    )

    cli.main()

    assert captured["selected_sources"] == ["springer"]
    assert captured["springer_api_key"] == "secret"
    assert captured["jsonl_progress"] is True


def test_mcp_text_and_api_key_tools(monkeypatch, tmp_path):
    def fake_verify_text(text, **kwargs):
        assert text == "A pasted reference"
        assert kwargs["output_dir"] == str(tmp_path)
        return {
            "summary": {
                "total": 1,
                "found": 1,
                "not_found": 0,
                "needs_review": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 1,
                "output_dir": kwargs["output_dir"],
                "report_summary": "MCP checked text.",
            },
            "results": [
                {
                    "key": "ref[1]",
                    "title": "A pasted reference",
                    "status": "found",
                    "risk_level": "low",
                    "source": "FakeSource",
                    "suggested_action": "No action.",
                }
            ],
        }

    monkeypatch.setattr(mcp_server, "verify_text", fake_verify_text)
    response = mcp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "check_reference_text",
                "arguments": {
                    "text": "A pasted reference",
                    "output_dir": str(tmp_path),
                    "sources": "crossref",
                },
            },
        }
    )
    assert response["result"]["isError"] is False
    assert "MCP checked text." in response["result"]["content"][0]["text"]

    monkeypatch.setattr(
        mcp_server,
        "test_api_keys",
        lambda **kwargs: {
            "summary": {"total": 1, "ok": 1, "failed": 0, "skipped": 0},
            "results": [{"name": "Springer", "status": "ok", "message": "connected"}],
        },
    )
    api_response = mcp_server.handle_message(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "test_reference_api_keys",
                "arguments": {"sources": "springer", "springer_api_key": "secret"},
            },
        }
    )
    assert api_response["result"]["isError"] is False
    assert "Springer" in api_response["result"]["content"][0]["text"]


def test_browser_extension_manifest_and_javascript_syntax():
    extension_dir = Path("browser_extension/refchecker_claude")
    manifest = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 3
    assert manifest["background"]["service_worker"] == "background.js"
    assert "storage" in manifest["permissions"]
    assert "http://127.0.0.1:8765/*" in manifest["host_permissions"]
    for icon_path in manifest["icons"].values():
        assert (extension_dir / icon_path).exists()

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not available for extension syntax checks")
    for script in ["background.js", "content.js", "popup.js"]:
        completed = subprocess.run(
            [node, "--check", str(extension_dir / script)],
            check=False,
            text=True,
            capture_output=True,
        )
        assert completed.returncode == 0, completed.stderr
