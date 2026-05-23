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

    def fake_verify_entry(title, author, year, doi, threshold, email, use_openalex, use_dblp, url="", use_url_verify=True):
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
            "needs_review": "Yes",
            "review_reasons": "BibTeX 缺少 DOI，数据库 DOI 为 10.1234/example",
        }

    monkeypatch.setattr(backend, "verify_entry", fake_verify_entry)
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
    assert events[-1]["found"] == 1
    assert events[-1]["needs_review"] == 1
    assert result["summary"]["markdown_path"].endswith("report.md")
    assert (output_dir / "report.md").exists()
    assert (output_dir / "result.csv").exists()

    report = (output_dir / "report.md").read_text(encoding="utf-8")
    csv_text = (output_dir / "result.csv").read_text(encoding="utf-8-sig")
    assert "A Tiny Test" in report
    assert "FakeSource" in report
    assert "demo,found,Yes" in csv_text


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
                          use_openalex, use_dblp, url="", use_url_verify=True):
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

    monkeypatch.setattr(backend, "verify_entry", fake_verify_entry)
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
    assert events[-1]["found"] == 1
    assert events[-1]["needs_review"] == 0
    assert result["summary"]["markdown_path"].endswith("report.md")
    assert (output_dir / "report.md").exists()
    assert (output_dir / "result.csv").exists()

    report = (output_dir / "report.md").read_text(encoding="utf-8")
    csv_text = (output_dir / "result.csv").read_text(encoding="utf-8-sig")
    assert "A Test Paper" in report
    assert "FakeSource" in report
