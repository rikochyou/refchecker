from refchecker import http_server


def test_check_text_payload_returns_browser_friendly_json(tmp_path, monkeypatch):
    def fake_verify_text(text, **kwargs):
        assert kwargs["search_mode"] == "parallel"
        assert kwargs["doi_check"] == "auto"
        assert kwargs["llm_parse_mode"] == "auto"
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
                "markdown_path": str(tmp_path / "report.md"),
                "csv_path": str(tmp_path / "result.csv"),
                "report_summary": "Checked one reference.",
                "search_mode": kwargs["search_mode"],
                "source_order": "OpenAlex -> CrossRef",
                "actual_query_trace": "DOI exact check: mismatch; OpenAlex: found (100%)",
                "doi_check_status": "mismatch",
                "doi_resolved_url": "https://doi.org/10.1/wrong",
                "llm_parse_mode": kwargs["llm_parse_mode"],
                "parser_summary": "llm:1",
            },
            "results": [
                {
                    "key": "ref[1]",
                    "title": "Input title",
                    "matched_title": "Correct title",
                    "status": "found",
                    "risk_level": "low",
                    "confidence_score": 95,
                    "source": "CrossRef",
                    "doi_check": "mismatch",
                    "doi_reason": "Input DOI differs from database DOI.",
                    "bib_doi": "10.1/wrong",
                    "matched_doi": "10.1/right",
                    "fix_suggestion": "Use the database DOI candidate after manual confirmation.",
                    "fix_suggestion_basis": "CrossRef",
                    "standard_citation_available": "Yes",
                    "standard_citation_apa": "Lovelace, A. (1843). Correct title. https://doi.org/10.1/right",
                    "standard_citation_bibtex": "",
                    "search_mode": kwargs["search_mode"],
                    "source_order": "OpenAlex -> CrossRef",
                    "actual_query_trace": "DOI exact check: mismatch; OpenAlex: found (100%)",
                    "adopted_source": "OpenAlex",
                    "doi_check_status": "mismatch",
                    "doi_check_message": "DOI points to another paper.",
                    "doi_resolved_url": "https://doi.org/10.1/wrong",
                    "doi_target_title": "Wrong title",
                    "parser": "llm",
                    "llm_parse_mode": kwargs["llm_parse_mode"],
                }
            ],
        }

    monkeypatch.setattr(http_server, "verify_text", fake_verify_text)
    payload = http_server.check_text_payload({
        "text": "Lovelace, A. (1843). Input title. https://doi.org/10.1/wrong",
        "output_dir": str(tmp_path),
        "search_mode": "parallel",
        "doi_check": "auto",
        "llm_parse_mode": "auto",
        "disabled_sources": ["url"],
        "links": [
            {
                "text": "arxiv",
                "href": "https://example.com/not-an-arxiv-paper",
            }
        ],
    })

    assert payload["ok"] is True
    assert payload["summary"]["total"] == 1
    assert payload["priority_items"][0]["link_issue"] == "input_doi_mismatch"
    assert payload["priority_items"][0]["correct_url"] == "https://doi.org/10.1/right"
    assert "Correct title" in payload["corrected_references"]
    assert payload["summary"]["link_alerts"] == 1
    assert payload["summary"]["search_mode"] == "parallel"
    assert payload["summary"]["llm_parse_mode"] == "auto"
    assert payload["items"][0]["adopted_source"] == "OpenAlex"
    assert payload["items"][0]["doi_check_status"] == "mismatch"
    assert payload["items"][0]["parser"] == "llm"
    assert payload["link_checks"][0]["issue"] == "label_domain_mismatch"


def test_check_text_payload_can_check_link_labels_without_verifying_as_title(tmp_path, monkeypatch):
    called = False

    def fake_verify_text(text, **kwargs):
        nonlocal called
        called = True
        return {"summary": {}, "results": []}

    monkeypatch.setattr(http_server, "verify_text", fake_verify_text)
    payload = http_server.check_text_payload({
        "text": "arxiv PNAS",
        "output_dir": str(tmp_path),
        "links_only": True,
        "links": [
            {"text": "arxiv", "href": "https://example.com/not-arxiv"},
            {"text": "PNAS", "href": "https://example.com/not-pnas"},
        ],
    })

    assert called is False
    assert payload["summary"]["total"] == 0
    assert payload["summary"]["link_checks"] == 2
    assert payload["summary"]["link_alerts"] == 2
    assert payload["link_checks"][1]["issue"] == "label_domain_mismatch"


def test_check_text_payload_links_only_with_doi_runs_doi_verification(tmp_path, monkeypatch):
    called = False

    def fake_verify_text(text, **kwargs):
        nonlocal called
        called = True
        assert kwargs["search_mode"] == "strict"
        assert kwargs["doi_check"] == "auto"
        return {
            "summary": {
                "total": 1,
                "found": 1,
                "not_found": 0,
                "needs_review": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
                "output_dir": kwargs["output_dir"],
                "search_mode": "strict",
                "source_order": "OpenAlex -> CrossRef",
                "actual_query_trace": "DOI exact check: matched",
                "doi_check_status": "matched",
            },
            "results": [
                {
                    "key": "ref[1]",
                    "title": "https://doi.org/10.1/example",
                    "matched_title": "Resolved DOI title",
                    "status": "found",
                    "risk_level": "none",
                    "source": "DOI exact check",
                    "adopted_source": "DOI exact check",
                    "doi_check_status": "matched",
                    "doi_target_title": "Resolved DOI title",
                }
            ],
        }

    monkeypatch.setattr(http_server, "verify_text", fake_verify_text)
    payload = http_server.check_text_payload({
        "text": "https://doi.org/10.1/example",
        "output_dir": str(tmp_path),
        "links_only": True,
        "links": [{"text": "DOI", "href": "https://doi.org/10.1/example"}],
    })

    assert called is True
    assert payload["summary"]["doi_check_status"] == "matched"
    assert payload["items"][0]["doi_target_title"] == "Resolved DOI title"


def test_check_text_payload_flags_target_title_mismatch(tmp_path, monkeypatch):
    from refchecker import link_context

    def fake_verify_text(text, **kwargs):
        return {
            "summary": {"total": 0, "found": 0, "not_found": 0, "needs_review": 0},
            "results": [],
        }

    def fake_fetch_target_metadata(url):
        return {
            "source": "arXiv",
            "id": "2505.12387",
            "title": "A Completely Different Paper Title",
            "authors": ["Alice Example"],
            "year": "2025",
            "url": url,
        }

    monkeypatch.setattr(http_server, "verify_text", fake_verify_text)
    monkeypatch.setattr(link_context, "_fetch_target_metadata", fake_fetch_target_metadata)
    payload = http_server.check_text_payload({
        "text": "https://arxiv.org/abs/2505.12387",
        "output_dir": str(tmp_path),
        "links_only": True,
        "links": [
            {
                "text": "How Do Language Models Speak Languages? A Case Study on Unintended Code-Switching",
                "href": "https://arxiv.org/abs/2505.12387",
                "surroundingText": "How Do Language Models Speak Languages? A Case Study on Unintended Code-Switching\nAuthors: Yuxin Xiao",
            }
        ],
    })

    assert payload["summary"]["link_alerts"] == 1
    assert payload["link_checks"][0]["issue"] == "target_title_mismatch"
    assert payload["link_checks"][0]["target_title"] == "A Completely Different Paper Title"
