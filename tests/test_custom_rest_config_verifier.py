import csv
import json

import pytest

from refchecker import config, custom_rest, verifier
from refchecker.author import parse_author_name


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_source_selection_ordering_and_invalid_values():
    assert config.parse_source_selection("crossref, s2, arxiv, s2") == [
        "crossref",
        "semantic-scholar",
        "arxiv",
    ]
    with pytest.raises(ValueError):
        config.parse_source_selection("crossref,unknown-source")

    order = config.build_source_order(["url", "custom:lab", "openalex"], ["custom:extra"])
    assert "url" not in order
    assert order[:2] == ["custom:lab", "openalex"]
    assert "custom:extra" in order
    assert config.source_selected(None, "crossref", default=True) is True
    assert config.source_selected(["openalex"], "crossref", default=True) is False


def test_api_key_response_classifier_handles_auth_limit_and_payload_errors():
    invalid = config._classify_api_key_response(
        "core", "CORE", "https://api.core", FakeResponse(status_code=403), {}, None
    )
    limited = config._classify_api_key_response(
        "core", "CORE", "https://api.core", FakeResponse(status_code=429), {}, None
    )
    api_error = config._classify_api_key_response(
        "core",
        "CORE",
        "https://api.core",
        FakeResponse({"message": "invalid API key"}, status_code=200),
        {"message": "invalid API key"},
        0,
    )

    assert invalid["status"] == "invalid_key"
    assert limited["status"] == "rate_limited"
    assert api_error["status"] == "invalid_key"


def test_custom_rest_profile_normalization_and_nested_search(monkeypatch):
    profiles = custom_rest.normalize_profiles(
        [
            {
                "id": "Lab Search",
                "name": "Lab Search",
                "endpoint": "https://api.example.test/search",
                "authType": "bearer",
                "apiKey": "secret",
                "queryParams": '{"query":"{title}", "year":"{year}", "email":"{email}"}',
                "headers": '{"X-Client":"{email}"}',
                "resultsPath": "payload.items",
                "titlePath": "metadata.title",
                "authorsPath": "metadata.authors",
                "yearPath": "metadata.date",
                "doiPath": "ids.doi",
                "urlPath": "links.0.url",
                "venuePath": "metadata.venue",
            },
            {"id": "disabled", "endpoint": "https://disabled", "enabled": False},
        ]
    )
    assert len(profiles) == 1
    assert profiles[0]["sourceKey"] == "custom:lab-search"

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse(
            {
                "payload": {
                    "items": [
                        {"metadata": {"title": "Wrong", "authors": ["Nobody"], "date": "1999"}},
                        {
                            "metadata": {
                                "title": "A Custom Source Paper",
                                "authors": [{"name": "Ada Lovelace"}],
                                "date": "1843-01-01",
                                "venue": "Custom Journal",
                            },
                            "ids": {"doi": "https://doi.org/10.1000/CUSTOM"},
                            "links": [{"url": "https://example.test/paper"}],
                            "type": "article",
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(custom_rest.requests, "get", fake_get)
    result = custom_rest.search_custom_rest(
        profiles[0],
        "A Custom Source Paper",
        "Lovelace, Ada",
        "1843",
        0.85,
        "ada@example.test",
    )

    assert result["found"] is True
    assert result["source"] == "Lab Search"
    assert result["matched_title"] == "A Custom Source Paper"
    assert result["doi"] == "10.1000/custom"
    assert result["year"] == "1843"
    assert result["venue"] == "Custom Journal"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["headers"]["X-Client"] == "ada@example.test"
    assert captured["params"]["query"] == "A Custom Source Paper"


def test_custom_rest_profile_connectivity_statuses(monkeypatch):
    profile = {
        "id": "custom",
        "name": "Custom API",
        "endpoint": "https://api.example.test/search",
        "resultsPath": "results",
    }

    monkeypatch.setattr(
        custom_rest.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({"results": [{"title": "x"}]}, status_code=200),
    )
    ok = custom_rest.test_custom_rest_profile(profile)
    assert ok["ok"] is True
    assert ok["status"] == "ok"
    assert ok["records"] == 1

    monkeypatch.setattr(
        custom_rest.requests,
        "get",
        lambda *args, **kwargs: FakeResponse({"error": "no"}, status_code=401),
    )
    invalid = custom_rest.test_custom_rest_profile(profile)
    assert invalid["ok"] is False
    assert invalid["status"] == "invalid_key"


def test_custom_rest_web_evidence_profile_returns_clickable_candidates(monkeypatch):
    profile = custom_rest.normalize_profiles(
        {
            "id": "brave-search",
            "name": "Brave Web Evidence",
            "endpoint": "https://api.search.brave.com/res/v1/web/search",
            "authType": "header",
            "apiKeyHeader": "X-Subscription-Token",
            "apiKey": "secret",
            "evidenceType": "web",
            "queryParams": {"q": '"{title}" DOI scholarly article'},
            "resultsPath": "web.results",
            "titlePath": "title",
            "urlPath": "url",
            "venuePath": "profile.name",
            "snippetPath": "description",
        }
    )[0]

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(
            {
                "web": {
                    "results": [
                        {
                            "title": "A Brave Evidence Paper",
                            "url": "https://publisher.example/paper",
                            "description": "Publisher landing page for the paper.",
                            "profile": {"name": "publisher.example"},
                            "type": "search_result",
                        },
                        {
                            "title": "A Brave Evidence Paper PDF",
                            "url": "https://university.example/paper.pdf",
                            "description": "PDF mirror.",
                            "profile": {"name": "university.example"},
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(custom_rest.requests, "get", fake_get)
    result = custom_rest.search_custom_rest(
        profile,
        "A Brave Evidence Paper",
        "",
        "",
        0.85,
        "",
    )

    assert result["found"] is True
    assert result["web_evidence"] == "Yes"
    assert result["evidence_kind"] == "web"
    assert "https://publisher.example/paper" in result["web_evidence_links"]
    assert result["web_evidence_results"][0]["url"] == "https://publisher.example/paper"
    assert "web evidence only" in result["reason"]

    row = {
        "key": "brave",
        "title": "A Brave Evidence Paper",
        **result,
        "author_check": "unknown",
        "year_check": "unknown",
        "doi_check": "unknown",
        "needs_review": "No",
    }
    verifier.apply_product_assessment(row)
    assert row["risk_level"] == "medium"
    assert row["confidence_score"] <= 64
    assert row["standard_citation_available"] == "No"


def test_doi_exact_check_statuses(monkeypatch):
    monkeypatch.setattr(
        verifier._sources,
        "search_crossref_by_doi",
        lambda doi, title, email: {
            "found": True,
            "matched_title": "Correct DOI Title",
            "similarity": 1.0,
            "source": "CrossRef(DOI)",
            "author_list": [parse_author_name(given="Ada", family="Lovelace")],
            "authors": "Ada Lovelace",
            "year": "1843",
            "doi": doi,
            "url": f"https://doi.org/{doi}",
        },
    )
    matched = verifier.run_doi_exact_check(
        title="Correct DOI Title",
        author="Lovelace, Ada",
        year="1843",
        doi="10.1000/demo",
        threshold=0.85,
        email="",
    )
    assert matched["doi_check_status"] == verifier.DOI_STATUS_MATCHED
    assert matched["doi_target_title"] == "Correct DOI Title"

    mismatch = verifier.run_doi_exact_check(
        title="Different Input Title",
        author="Lovelace, Ada",
        year="1843",
        doi="10.1000/demo",
        threshold=0.95,
        email="",
    )
    assert mismatch["doi_check_status"] == verifier.DOI_STATUS_MISMATCH
    assert "title mismatch" in mismatch["doi_check_message"]

    monkeypatch.setattr(
        verifier._sources,
        "search_crossref_by_doi",
        lambda doi, title, email: {"found": False, "reason": "request timeout"},
    )
    unresolved = verifier.run_doi_exact_check(
        title="Any",
        author="",
        year="",
        doi="10.1000/unresolved",
        threshold=0.85,
        email="",
    )
    assert unresolved["doi_check_status"] == verifier.DOI_STATUS_UNRESOLVED

    off = verifier.run_doi_exact_check(
        title="Any",
        author="",
        year="",
        doi="10.1000/off",
        threshold=0.85,
        email="",
        doi_check="off",
    )
    assert off["doi_check_strategy"] == "off"
    assert off["doi_check_status"] == verifier.DOI_STATUS_NOT_PROVIDED


def test_verify_entry_custom_rest_and_url_fallback(monkeypatch):
    profile = custom_rest.normalize_profiles(
        {
            "id": "lab",
            "name": "Lab REST",
            "endpoint": "https://api.example.test/search",
            "resultsPath": "items",
        }
    )[0]

    monkeypatch.setattr(
        verifier._custom_rest,
        "search_custom_rest",
        lambda profile, title, author, year, threshold, email: {
            "found": True,
            "matched_title": title,
            "similarity": 1.0,
            "source": profile["name"],
            "author_list": [parse_author_name(given="Ada", family="Lovelace")],
            "authors": "Ada Lovelace",
            "year": year,
            "doi": "10.1000/custom",
            "url": "https://example.test/paper",
        },
    )
    custom = verifier.verify_entry(
        "A Custom REST Paper",
        "Lovelace, Ada",
        "1843",
        "",
        0.85,
        "",
        use_openalex=False,
        use_dblp=False,
        use_semantic_scholar=False,
        use_arxiv=False,
        use_pubmed=False,
        use_crossref=False,
        use_url_verify=False,
        source_order=["custom:lab"],
        custom_rest_profiles=[profile],
    )
    assert custom["found"] is True
    assert custom["source"] == "Lab REST"
    assert custom["source_order_keys"] == "custom:lab"

    monkeypatch.setattr(
        verifier._url_verify,
        "verify_url_resource",
        lambda url, title, author, year, email: {
            "found": True,
            "matched_title": url,
            "similarity": 0.0,
            "source": "URL(Web)",
            "author_list": [],
            "authors": "",
            "year": "",
            "doi": "",
            "url": url,
        },
    )
    web = verifier.verify_entry(
        "Only URL Resource",
        "",
        "",
        "",
        0.85,
        "",
        use_openalex=False,
        use_dblp=False,
        use_semantic_scholar=False,
        use_arxiv=False,
        use_pubmed=False,
        use_crossref=False,
        url="https://example.test/resource",
        use_url_verify=True,
    )
    assert web["found"] is True
    assert web["source"] == "URL(Web)"
    assert "URL verification" in web["arbitration_reason"]


def test_product_assessment_standard_citations_and_csv(tmp_path):
    row = {
        "key": "lovelace1843",
        "title": "Input",
        "status": "found",
        "found": True,
        "matched_title": "Notes on the Analytical Engine",
        "similarity": 1.0,
        "source": "CrossRef",
        "venue": "Scientific Memoirs",
        "type": "journal-article",
        "year": "1843",
        "doi": "10.1000/lovelace",
        "author_list": [parse_author_name(given="Ada", family="Lovelace")],
        "author_check": "exact",
        "year_check": "exact",
        "doi_check": "exact",
        "first_author_match": "Yes",
        "needs_review": "No",
        "review_reasons": "",
    }
    verifier.apply_product_assessment(row)
    assert row["risk_level"] == "none"
    assert row["standard_citation_available"] == "Yes"
    assert "Lovelace, A." in row["standard_citation_apa"]
    assert "@article{Lovelace1843" in row["standard_citation_bibtex"]

    csv_path = tmp_path / "result.csv"
    verifier.write_csv_report(str(csv_path), [row])
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["key"] == "lovelace1843"
    assert rows[0]["risk_level"] == "none"
    assert rows[0]["standard_citation_available"] == "Yes"
    json.loads(rows[0]["standard_citation_json"])
