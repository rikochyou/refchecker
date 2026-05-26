import contextlib
import io
import json
from pathlib import Path

import check_bib_crossref as backend


def test_verify_bib_file_jsonl_and_reports(tmp_path, monkeypatch):
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
    output_dir = tmp_path / "out"

    def fake_verify_entry(title, author, year, doi, threshold, email, use_openalex, use_dblp,
                          use_semantic_scholar=True, use_arxiv=True, use_pubmed=True,
                          url="", use_url_verify=True, **kwargs):
        return {
            "found": True,
            "status": "found",
            "matched_title": title,
            "similarity": 1.0,
            "source": "FakeSource",
            "venue": "Test Venue",
            "year": year,
            "type": "article",
            "authors": "Ada Lovelace",
            "doi": "10.1234/example",
            "url": "https://example.test",
            "reason": "",
            "author_check": "exact",
            "author_reason": "作者一致",
            "bib_authors": "Ada Lovelace",
            "matched_authors": "Ada Lovelace",
            "matched_author_count": 1,
            "bib_author_count": 1,
            "missing_authors": "",
            "extra_authors": "",
            "author_order_mismatch": False,
            "first_author_match": True,
            "year_check": "exact",
            "year_reason": "年份一致",
            "bib_year": year,
            "matched_year": year,
            "doi_check": "missing_in_bib",
            "doi_reason": "BibTeX 缺少 DOI，数据库 DOI 为 10.1234/example",
            "bib_doi": "",
            "matched_doi": "10.1234/example",
            "needs_review": "No",
            "review_reasons": "",
        }

    monkeypatch.setattr(backend.verifier, "verify_entry", fake_verify_entry)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = backend.verify_bib_file(
            str(bib_path),
            output_dir=str(output_dir),
            jsonl_progress=True,
            human_output=True,
            delay=0,
        )

    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [event["type"] for event in events] == [
        "started",
        "entry_started",
        "entry_finished",
        "summary",
    ]
    entry_result = events[2]["result"]
    assert entry_result["risk_level"] == "low"
    assert entry_result["confidence_score"] >= 80
    assert "建议补充 DOI" in entry_result["suggested_action"]
    assert events[-1]["found"] == 1
    assert events[-1]["needs_review"] == 0
    assert events[-1]["low_risk"] == 1
    assert result["summary"]["markdown_path"].endswith("report.md")
    assert "html_path" not in result["summary"]
    assert (output_dir / "report.md").exists()
    assert not (output_dir / "report.html").exists()
    assert (output_dir / "result.csv").exists()

    report = (output_dir / "report.md").read_text(encoding="utf-8")
    csv_text = (output_dir / "result.csv").read_text(encoding="utf-8-sig")
    assert "A Tiny Test" in report
    assert "FakeSource" in report
    assert "需要人工核查的高风险条目" not in report
    assert "置信度是 RefChecker" in report
    assert "不是文献真实存在的概率" in report
    assert "risk_level" in csv_text
    assert "demo,found,No,low" in csv_text


def test_parse_reference_text():
    ref = (
        "Anderson, J. S., Druzgal, T. J., & Froehlich, A. (2011). "
        "Decreased interhemispheric functional connectivity in autism. "
        "Cerebral Cortex, 21(5), 1134-1146. "
        "https://doi.org/10.1093/cercor/bhq190"
    )
    parsed = backend.parse_reference_text(ref)
    assert parsed["doi"] == "10.1093/cercor/bhq190"
    assert parsed["year"] == "2011"
    assert "Anderson" in parsed["authors"]
    assert "Druzgal" in parsed["authors"]
    assert "Froehlich" in parsed["authors"]
    assert "and" in parsed["authors"]
    assert "Decreased interhemispheric functional connectivity" in parsed["title"]


def test_apa_authors_to_bibtex():
    assert backend._apa_authors_to_bibtex("Benjamini, Y., & Hochberg, Y.") == \
        "Benjamini, Y. and Hochberg, Y."
    assert backend._apa_authors_to_bibtex("Beres, A. M.") == "Beres, A. M."
    long_authors = "Han, Y. M. Y., Chan, M.-C., Chan, M. M. Y., Yeung, M. K., & Chan, A. S."
    result = backend._apa_authors_to_bibtex(long_authors)
    assert " and " in result
    assert result.count(" and ") == 4  # 5 authors = 4 "and"s


def test_verify_docx_file_jsonl_and_reports(tmp_path, monkeypatch):
    """验证 DOCX 文件验证流程：JSONL 事件 + 报告文件生成。"""
    try:
        from docx import Document as DocxDocument
    except ImportError:
        import pytest
        pytest.skip("python-docx 未安装")

    docx_path = tmp_path / "refs.docx"
    doc = DocxDocument()
    # 添加 "Bibliography" 样式的段落
    para = doc.add_paragraph(
        "Smith, J. (2020). A Test Paper About Something. "
        "Journal of Testing, 10(2), 100-110. "
        "https://doi.org/10.1234/test.2020",
    )
    para.style = doc.styles["Bibliography"] if "Bibliography" in [s.name for s in doc.styles] else doc.styles["Normal"]
    doc.save(str(docx_path))

    output_dir = tmp_path / "out"

    def fake_verify_entry(title, author, year, doi, threshold, email,
                          use_openalex, use_dblp,
                          use_semantic_scholar=True, use_arxiv=True, use_pubmed=True,
                          url="", use_url_verify=True, **kwargs):
        return {
            "found": True,
            "status": "found",
            "matched_title": "A Test Paper About Something",
            "similarity": 1.0,
            "source": "FakeSource",
            "venue": "Journal of Testing",
            "year": year,
            "type": "article",
            "authors": "Smith, J.",
            "doi": doi or "10.1234/test.2020",
            "url": "",
            "reason": "",
            "author_check": "exact",
            "author_reason": "作者一致",
            "bib_authors": "Smith, J.",
            "matched_authors": "Smith, J.",
            "matched_author_count": 1,
            "bib_author_count": 1,
            "missing_authors": "",
            "extra_authors": "",
            "author_order_mismatch": False,
            "first_author_match": True,
            "year_check": "exact",
            "year_reason": "年份一致",
            "bib_year": year,
            "matched_year": year,
            "doi_check": "exact",
            "doi_reason": "DOI 一致",
            "bib_doi": doi,
            "matched_doi": doi or "10.1234/test.2020",
            "needs_review": "No",
            "review_reasons": "",
        }

    monkeypatch.setattr(backend.verifier, "verify_entry", fake_verify_entry)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = backend.verify_docx_file(
            str(docx_path),
            output_dir=str(output_dir),
            jsonl_progress=True,
            human_output=True,
            delay=0,
        )

    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [event["type"] for event in events] == [
        "started",
        "entry_started",
        "entry_finished",
        "summary",
    ]
    assert events[2]["result"]["risk_level"] == "none"
    assert events[2]["result"]["suggested_action"] == "无需处理。"
    assert events[-1]["found"] == 1
    assert events[-1]["needs_review"] == 0
    assert result["summary"]["markdown_path"].endswith("report.md")
    assert "html_path" not in result["summary"]
    assert (output_dir / "report.md").exists()
    assert not (output_dir / "report.html").exists()
    assert (output_dir / "result.csv").exists()

    report = (output_dir / "report.md").read_text(encoding="utf-8")
    csv_text = (output_dir / "result.csv").read_text(encoding="utf-8-sig")
    assert "A Test Paper" in report
    assert "FakeSource" in report


def test_product_assessment_flags_high_risk_doi_mismatch():
    row = {
        "key": "bad-doi",
        "title": "A Paper",
        "status": "found",
        "found": True,
        "matched_title": "A Paper",
        "similarity": 1.0,
        "source": "CrossRef(DOI)",
        "author_check": "exact",
        "author_reason": "作者一致",
        "first_author_match": "Yes",
        "year_check": "exact",
        "year_reason": "年份一致",
        "doi_check": "mismatch",
        "doi_reason": "DOI 不一致",
        "bib_year": "2024",
        "matched_year": "2024",
        "bib_doi": "10.1/wrong",
        "matched_doi": "10.1/right",
        "needs_review": "No",
        "review_reasons": "",
    }

    backend.apply_product_assessment(row)

    assert row["risk_level"] == "high"
    assert row["needs_review"] == "Yes"
    assert "优先核对 DOI" in row["suggested_action"]
    assert row["confidence_score"] < 90


def test_medium_risk_year_mismatch_is_not_mandatory_review():
    row = {
        "key": "year-warning",
        "title": "A Paper",
        "status": "found",
        "found": True,
        "matched_title": "A Paper",
        "similarity": 1.0,
        "source": "OpenAlex",
        "author_check": "exact",
        "author_reason": "作者一致",
        "first_author_match": "Yes",
        "year_check": "mismatch",
        "year_reason": "年份不一致：BibTeX 2024，数据库 2023",
        "doi_check": "missing_in_bib",
        "doi_reason": "BibTeX 缺少 DOI，数据库 DOI 为 10.1/example",
        "bib_year": "2024",
        "matched_year": "2023",
        "bib_doi": "",
        "matched_doi": "10.1/example",
        "needs_review": "Yes",
        "review_reasons": "旧策略会把年份差异计入需复核",
    }

    backend.apply_product_assessment(row)

    assert row["risk_level"] == "medium"
    assert row["needs_review"] == "No"
    assert row["review_reasons"] == ""
    assert "核对年份" in row["suggested_action"]


def test_title_similarity_85_to_90_is_sampling_not_mandatory_review():
    result = {
        "key": "close-title",
        "title": "A Paper With a Slightly Different Subtitle",
        "status": "found",
        "found": True,
        "matched_title": "A Paper With Slightly Different Subtitle",
        "similarity": 0.87,
        "source": "CrossRef",
        "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
        "authors": "Ada Lovelace",
        "year": "1843",
        "doi": "10.1/example",
        "url": "",
        "reason": "",
    }

    backend.enrich_result(
        result,
        bib_author="Lovelace, Ada",
        bib_year="1843",
        bib_doi="10.1/example",
    )
    backend.apply_product_assessment(result)

    assert result["risk_level"] == "medium"
    assert result["needs_review"] == "No"
    assert result["review_reasons"] == ""
    assert "核对标题" in result["suggested_action"]


def test_verify_entry_uses_semantic_scholar_fallback(monkeypatch):
    monkeypatch.setattr(
        backend.sources,
        "search_crossref",
        lambda title, author, year, threshold, email: {
            "found": False,
            "similarity": 0.0,
            "reason": "CrossRef 无返回结果",
        },
    )
    monkeypatch.setattr(
        backend.sources,
        "search_semantic_scholar",
        lambda title, author, year, threshold, email: {
            "found": True,
            "matched_title": title,
            "similarity": 1.0,
            "source": "Semantic Scholar",
            "venue": "Test Venue",
            "year": year,
            "type": "paper",
            "authors": "Ada Lovelace",
            "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
            "doi": "10.1/example",
            "url": "https://www.semanticscholar.org/paper/example",
            "reason": "",
        },
    )

    result = backend.verify_entry(
        "A Semantic Scholar Paper",
        "Lovelace, Ada",
        "1843",
        "",
        0.85,
        "",
        use_openalex=False,
        use_dblp=False,
        use_semantic_scholar=True,
        use_arxiv=False,
        use_pubmed=False,
        use_url_verify=False,
    )

    assert result["found"] is True
    assert result["source"] == "Semantic Scholar"
    assert result["author_check"] == "exact"
    assert result["doi_check"] == "missing_in_bib"


def test_verify_entry_global_arbitration_prefers_crossref_high_confidence(monkeypatch):
    calls = []

    def fake_crossref_by_doi(doi, title, email):
        calls.append("crossref-doi")
        return {
            "found": True,
            "matched_title": title,
            "similarity": 1.0,
            "source": "CrossRef(DOI)",
            "venue": "CrossRef",
            "year": "1843",
            "type": "journal-article",
            "authors": "Ada Lovelace",
            "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
            "doi": doi,
            "url": f"https://doi.org/{doi}",
            "reason": "",
            "doi_exact_query": True,
        }

    def fake_semantic(title, author, year, threshold, email):
        calls.append("semantic-scholar")
        return {
            "found": True,
            "matched_title": "A different Semantic Scholar Paper",
            "similarity": 0.08,
            "source": "Semantic Scholar",
            "venue": "Test Venue",
            "year": year,
            "type": "paper",
            "authors": "Ada Lovelace",
            "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
            "doi": "10.1/example",
            "url": "https://www.semanticscholar.org/paper/example",
            "reason": "",
        }

    monkeypatch.setattr(backend.sources, "search_crossref_by_doi", fake_crossref_by_doi)
    monkeypatch.setattr(backend.sources, "search_semantic_scholar", fake_semantic)

    result = backend.verify_entry(
        "A Semantic Scholar Paper",
        "Lovelace, Ada",
        "1843",
        "10.1/example",
        0.85,
        "",
        use_openalex=False,
        use_dblp=False,
        use_semantic_scholar=True,
        use_arxiv=False,
        use_pubmed=False,
        use_crossref=True,
        use_url_verify=False,
        source_order=["semantic-scholar", "crossref"],
    )

    assert result["found"] is True
    assert result["source"] == "CrossRef(DOI)"
    assert result["candidate_count"] == 2
    assert "Semantic Scholar" in result["alternative_candidates"]
    assert "并发核验" in result["arbitration_reason"]
    assert set(calls) == {"semantic-scholar", "crossref-doi"}


def test_verify_entry_uses_source_order_as_tiebreaker(monkeypatch):
    def fake_crossref(title, author, year, threshold, email):
        return {
            "found": True,
            "matched_title": title,
            "similarity": 1.0,
            "source": "CrossRef",
            "venue": "CrossRef",
            "year": year,
            "type": "journal-article",
            "authors": "Ada Lovelace",
            "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
            "doi": "10.1/example",
            "url": "https://doi.org/10.1/example",
            "reason": "",
        }

    def fake_semantic(title, author, year, threshold, email):
        return {
            "found": True,
            "matched_title": title,
            "similarity": 1.0,
            "source": "Semantic Scholar",
            "venue": "Test Venue",
            "year": year,
            "type": "paper",
            "authors": "Ada Lovelace",
            "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
            "doi": "10.1/example",
            "url": "https://www.semanticscholar.org/paper/example",
            "reason": "",
        }

    monkeypatch.setattr(backend.sources, "search_crossref", fake_crossref)
    monkeypatch.setattr(backend.sources, "search_semantic_scholar", fake_semantic)

    result = backend.verify_entry(
        "A Tie Breaker Paper",
        "Lovelace, Ada",
        "1843",
        "",
        0.85,
        "",
        use_openalex=False,
        use_dblp=False,
        use_semantic_scholar=True,
        use_arxiv=False,
        use_pubmed=False,
        use_crossref=True,
        use_url_verify=False,
        source_order=["semantic-scholar", "crossref"],
    )

    assert result["found"] is True
    assert result["source"] == "Semantic Scholar"
    assert result["candidate_count"] == 2
    assert "CrossRef" in result["alternative_candidates"]


def test_verify_entry_uses_crossref_doi_when_crossref_is_first(monkeypatch):
    calls = []

    def fake_crossref_by_doi(doi, title, email):
        calls.append("crossref-doi")
        return {
            "found": True,
            "matched_title": title,
            "similarity": 1.0,
            "source": "CrossRef(DOI)",
            "venue": "CrossRef",
            "year": "1843",
            "type": "journal-article",
            "authors": "Ada Lovelace",
            "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
            "doi": doi,
            "url": f"https://doi.org/{doi}",
            "reason": "",
            "doi_exact_query": True,
        }

    def fake_semantic(title, author, year, threshold, email):
        calls.append("semantic-scholar")
        return {"found": False, "similarity": 0.0, "reason": "not reached"}

    monkeypatch.setattr(backend.sources, "search_crossref_by_doi", fake_crossref_by_doi)
    monkeypatch.setattr(backend.sources, "search_semantic_scholar", fake_semantic)

    result = backend.verify_entry(
        "A CrossRef DOI Paper",
        "Lovelace, Ada",
        "1843",
        "10.1/example",
        0.85,
        "",
        use_openalex=False,
        use_dblp=False,
        use_semantic_scholar=True,
        use_arxiv=False,
        use_pubmed=False,
        use_crossref=True,
        use_url_verify=False,
        source_order=["crossref", "semantic-scholar"],
    )

    assert result["found"] is True
    assert result["source"] == "CrossRef(DOI)"
    assert "crossref-doi" in calls


def test_source_selection_aliases_and_api_key_source(monkeypatch):
    selected = backend.parse_source_selection("crossref, s2, arxiv, ieee-xplore")
    assert selected == ["crossref", "semantic-scholar", "arxiv", "ieee"]

    monkeypatch.setattr(
        backend.sources,
        "search_springer",
        lambda title, author, year, threshold, api_key: {
            "found": True,
            "matched_title": title,
            "similarity": 1.0,
            "source": "Springer Nature",
            "venue": "Springer",
            "year": year,
            "type": "journal-article",
            "authors": "Ada Lovelace",
            "author_list": [backend.parse_author_name(given="Ada", family="Lovelace")],
            "doi": "10.1/springer",
            "url": "https://link.springer.com/article/10.1/springer",
            "reason": "",
        },
    )

    result = backend.verify_entry(
        "A Springer Paper",
        "Lovelace, Ada",
        "1843",
        "",
        0.85,
        "",
        use_crossref=False,
        use_openalex=False,
        use_semantic_scholar=False,
        use_arxiv=False,
        use_pubmed=False,
        use_dblp=False,
        use_springer=True,
        springer_api_key="test-key",
        use_url_verify=False,
    )

    assert result["found"] is True
    assert result["source"] == "Springer Nature"
    assert result["author_check"] == "exact"


def test_api_key_connectivity_uses_source_specific_routes(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({
            "url": url,
            "params": params or {},
            "headers": headers or {},
            "timeout": timeout,
        })
        if "springernature" in url:
            return FakeResponse({"records": [{"title": "Machine learning"}]})
        if "ieeexploreapi" in url:
            return FakeResponse({"articles": [{"title": "Machine learning"}]})
        if "api.core.ac.uk" in url:
            return FakeResponse({"results": [{"title": "Machine learning"}]})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(backend.requests, "get", fake_get)

    result = backend.test_api_keys(
        selected_sources={"springer", "ieee", "core"},
        springer_api_key="springer-key",
        ieee_api_key="ieee-key",
        core_api_key="core-key",
        human_output=False,
    )

    assert result["summary"]["ok"] == 3
    assert [item["status"] for item in result["results"]] == ["ok", "ok", "ok"]
    assert calls[0]["url"] == "https://api.springernature.com/meta/v2/json"
    assert calls[0]["params"]["api_key"] == "springer-key"
    assert calls[1]["url"] == "https://ieeexploreapi.ieee.org/api/v1/search/articles"
    assert calls[1]["params"]["apikey"] == "ieee-key"
    assert calls[2]["url"] == "https://api.core.ac.uk/v3/search/works"
    assert calls[2]["headers"]["Authorization"] == "Bearer core-key"


def test_api_key_connectivity_reports_missing_selected_key():
    result = backend.test_api_keys(
        selected_sources={"springer"},
        springer_api_key="",
        human_output=False,
    )

    assert result["summary"]["skipped"] == 1
    assert result["results"][0]["source"] == "springer"
    assert result["results"][0]["status"] == "not_configured"
