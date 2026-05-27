import xml.etree.ElementTree as ET

import pytest

from refchecker import link_context, sources, url_verify


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, text="", url="https://example.test"):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def close(self):
        return None


def test_source_result_builders_normalize_provider_payloads():
    title = "A Shared Test Title"

    crossref = sources.build_crossref_result(
        {
            "title": [title],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "issued": {"date-parts": [[1843]]},
            "container-title": ["Journal of Tests"],
            "type": "journal-article",
            "DOI": "10.1000/ABC",
            "URL": "https://doi.org/10.1000/abc",
        },
        title,
    )
    assert crossref["source"] == "CrossRef"
    assert crossref["authors"] == "Ada Lovelace"
    assert crossref["similarity"] == 1.0

    openalex = sources.build_openalex_result(
        {
            "display_name": title,
            "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
            "publication_year": 1843,
            "primary_location": {"source": {"display_name": "Open Journal"}},
            "doi": "https://doi.org/10.1000/ABC",
            "id": "https://openalex.org/W1",
        },
        title,
    )
    assert openalex["doi"] == "10.1000/abc"
    assert openalex["venue"] == "Open Journal"

    semantic = sources.build_semantic_scholar_result(
        {
            "title": title,
            "authors": [{"name": "Ada Lovelace"}],
            "year": 1843,
            "venue": "S2 Venue",
            "publicationTypes": ["JournalArticle"],
            "externalIds": {"DOI": "10.1000/ABC"},
            "paperId": "paper1",
        },
        title,
    )
    assert semantic["url"].endswith("/paper/paper1")
    assert semantic["type"] == "JournalArticle"

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(
        """
        <entry xmlns="http://www.w3.org/2005/Atom">
          <title>A Shared Test Title</title>
          <id>https://arxiv.org/abs/2401.00001v2</id>
          <published>2024-01-01T00:00:00Z</published>
          <author><name>Ada Lovelace</name></author>
          <link rel="related" href="https://doi.org/10.1000/arxiv" />
        </entry>
        """
    )
    arxiv = sources.build_arxiv_result(entry, title, ns)
    assert arxiv["year"] == "2024"
    assert arxiv["doi"] == "10.1000/arxiv"

    pubmed = sources.build_pubmed_result(
        {
            "uid": "123",
            "title": f"{title}.",
            "authors": [{"name": "Lovelace A"}],
            "pubdate": "1843 Jan",
            "articleids": [{"idtype": "doi", "value": "10.1000/PUB"}],
            "fulljournalname": "PubMed Journal",
        },
        title,
    )
    assert pubmed["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert pubmed["doi"] == "10.1000/pub"

    ieee = sources.build_ieee_result(
        {
            "article_title": "<b>A Shared Test Title</b>",
            "authors": {"authors": [{"full_name": "Ada Lovelace"}]},
            "publication_year": "1843",
            "publication_title": "IEEE Tests",
            "doi": "10.1000/IEEE",
        },
        title,
    )
    assert ieee["matched_title"] == title
    assert ieee["doi"] == "10.1000/ieee"

    dblp = sources.build_dblp_result(
        {
            "title": "{A Shared Test Title}.",
            "authors": {"author": {"text": "Ada Lovelace"}},
            "year": "1843",
            "ee": "https://doi.org/10.1000/dblp",
        },
        title,
    )
    assert dblp["matched_title"] == title
    assert dblp["url"] == "https://doi.org/10.1000/dblp"


def test_search_crossref_picks_best_metadata_candidate(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse(
            {
                "message": {
                    "items": [
                        {
                            "title": ["Different Work"],
                            "author": [{"given": "Alan", "family": "Turing"}],
                            "issued": {"date-parts": [[1950]]},
                        },
                        {
                            "title": ["A Shared Test Title"],
                            "author": [{"given": "Ada", "family": "Lovelace"}],
                            "issued": {"date-parts": [[1843]]},
                            "DOI": "10.1000/right",
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(sources.requests, "get", fake_get)
    result = sources.search_crossref(
        "A Shared Test Title",
        "Lovelace, Ada",
        "1843",
        threshold=0.85,
        email="ada@example.test",
    )

    assert result["found"] is True
    assert result["matched_title"] == "A Shared Test Title"
    assert result["doi"] == "10.1000/right"
    assert captured["params"]["query.author"] == "Lovelace"
    assert "mailto:ada@example.test" in captured["headers"]["User-Agent"]


def test_url_verifiers_dispatch_and_normalize_metadata(monkeypatch):
    assert url_verify.detect_url_platform("https://huggingface.co/org/model") == "huggingface"
    assert url_verify.detect_url_platform("https://github.com/openai/codex") == "github"
    assert url_verify.detect_url_platform("https://example.com") == "general"

    def fake_get(url, headers=None, timeout=None):
        assert url == "https://api.github.com/repos/openai/codex"
        return FakeResponse(
            {
                "full_name": "openai/codex",
                "owner": {"login": "openai"},
                "created_at": "2025-01-01T00:00:00Z",
                "description": "A Shared Test Title",
                "stargazers_count": 42,
            }
        )

    monkeypatch.setattr(url_verify.requests, "get", fake_get)
    github = url_verify.verify_github(
        "https://github.com/openai/codex/blob/main/README.md",
        "A Shared Test Title",
        "",
        "",
    )
    assert github["found"] is True
    assert github["source"] == "URL(GitHub)"
    assert github["matched_title"] == "openai/codex"
    assert github["author_list"][0]["family"] == "openai"

    class FakeSession:
        def get(self, url, headers=None, timeout=None):
            assert url == "https://huggingface.co/api/datasets/org/data"
            return FakeResponse(
                {
                    "id": "org/data",
                    "author": "org",
                    "lastModified": "2024-02-03T00:00:00Z",
                    "tags": ["dataset", {"label": "paper"}],
                }
            )

    monkeypatch.setattr(url_verify.requests, "Session", lambda: FakeSession())
    hf = url_verify.verify_huggingface(
        "https://huggingface.co/datasets/org/data",
        "org/data",
        "",
        "",
    )
    assert hf["found"] is True
    assert hf["type"] == "dataset"
    assert hf["year"] == "2024"
    assert "dataset" in hf["tags"]


def test_general_url_head_get_fallback_and_dispatch(monkeypatch):
    calls = []

    def fake_head(url, headers=None, timeout=None, allow_redirects=None):
        calls.append(("head", url))
        return FakeResponse(status_code=405)

    def fake_get(url, headers=None, timeout=None, allow_redirects=None, stream=None):
        calls.append(("get", url))
        return FakeResponse(status_code=200)

    monkeypatch.setattr(url_verify.requests, "head", fake_head)
    monkeypatch.setattr(url_verify.requests, "get", fake_get)

    result = url_verify.verify_general_url("https://example.test/resource")
    assert result["found"] is True
    assert result["source"] == "URL(Web)"
    assert calls == [("head", "https://example.test/resource"), ("get", "https://example.test/resource")]

    monkeypatch.setattr(url_verify, "verify_general_url", lambda *args, **kwargs: {"source": "general"})
    assert url_verify.verify_url_resource("https://example.test")["source"] == "general"


@pytest.mark.parametrize(
    "link,issue,risk",
    [
        ({"text": "arXiv", "href": "https://example.com/not-arxiv"}, "label_domain_mismatch", "high"),
        ({"text": "https://arxiv.org/abs/2401.1", "href": "https://example.com/x"}, "visible_url_mismatch", "high"),
        ({"text": "paper", "href": "javascript:alert(1)"}, "unsafe_scheme", "high"),
        (
            {
                "text": "paper",
                "href": "https://tracker.example/?url=https%3A%2F%2Farxiv.org%2Fabs%2F2401.1",
            },
            "redirect_wrapper",
            "medium",
        ),
    ],
)
def test_browser_link_static_risk_rules(link, issue, risk):
    result = link_context.check_browser_link(link)
    assert result["issue"] == issue
    assert result["risk_level"] == risk


def test_browser_link_target_metadata_title_mismatch_and_dedup(monkeypatch):
    monkeypatch.setattr(
        link_context,
        "_fetch_target_metadata",
        lambda url: {
            "source": "arXiv",
            "title": "A Completely Different Target Paper",
            "authors": ["Ada Lovelace"],
            "year": "1843",
            "url": url,
        },
    )
    result = link_context.check_browser_link(
        {
            "text": "Expected Paper Title About Engines",
            "href": "https://arxiv.org/abs/2401.00001",
            "surroundingText": "Expected Paper Title About Engines\nAuthors: Example",
        },
        fetch_target=True,
    )
    assert result["issue"] == "target_title_mismatch"
    assert result["target_title"] == "A Completely Different Target Paper"
    assert result["target_title_similarity"] < 0.55

    checked = link_context.check_browser_links(
        [
            {"text": "arXiv", "href": "https://arxiv.org/abs/1"},
            {"text": "arXiv", "href": "https://arxiv.org/abs/1"},
            {"text": "DOI", "href": "https://doi.org/10.1000/demo"},
        ],
        max_links=2,
    )
    assert len(checked) == 1
