from refchecker.citation_consistency import (
    check_citation_consistency,
    check_text_citation_consistency,
    extract_body_citations,
    split_text_body_and_references,
)
from refchecker.docx_parser import parse_reference_text, parse_text_references


def test_parse_text_references_handles_apa_blank_lines_numbered_and_doi_only():
    refs = parse_text_references(
        "1. Lovelace, A. (1843). Notes on the analytical engine. Journal, 1, 1-2. "
        "https://doi.org/10.1000/love\n\n"
        "2. Turing, A. (1950). Computing machinery and intelligence. Mind, 59, 433-460."
    )

    assert len(refs) == 2
    assert refs[0]["paragraph"] == 1
    assert refs[0]["index"] == 0
    assert refs[0]["doi"] == "10.1000/love"
    assert "Notes on the analytical engine" in refs[0]["title"]
    assert refs[1]["year"] == "1950"

    doi_only = parse_reference_text("https://doi.org/10.1145/3368089.3409749")
    assert doi_only["doi"] == "10.1145/3368089.3409749"
    assert doi_only["title"] == ""
    assert doi_only["url"] == "https://doi.org/10.1145/3368089.3409749"


def test_parse_reference_text_strips_conference_pages_before_doi():
    ref = parse_reference_text(
        "Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). "
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. "
        "Proceedings of NAACL-HLT, 4171-4186. "
        "https://doi.org/10.18653/v1/N19-1423"
    )

    assert ref["title"] == (
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
    )
    assert ref["doi"] == "10.18653/v1/N19-1423"


def test_parse_reference_text_strips_arxiv_url_and_keeps_all_authors():
    ref = parse_reference_text(
        "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., "
        "Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). "
        "Attention is All You Need. Advances in Neural Information Processing Systems, 30. "
        "https://arxiv.org/abs/1706.03762"
    )

    assert ref["title"] == "Attention is All You Need"
    assert ref["url"] == "https://arxiv.org/abs/1706.03762"
    assert ref["authors"].count(" and ") == 7


def test_split_text_body_and_references_detects_heading_and_paragraph_numbers():
    parsed = split_text_body_and_references(
        "Lovelace (1843) introduced the notes.\n\n"
        "References\n\n"
        "Lovelace, A. (1843). Notes on the analytical engine. Journal."
    )

    assert parsed["has_reference_section"] is True
    assert parsed["body"][0]["paragraph"] == 1
    assert parsed["references"][0]["paragraph"] == 3
    assert "Lovelace" in parsed["reference_text"]


def test_citation_consistency_reports_missing_uncited_and_duplicate_signatures():
    body = [
        {
            "text": (
                "Smith (2020) is cited in the prose. "
                "A missing source also appears (Turing, 1950)."
            ),
            "paragraph": 1,
        }
    ]
    references = [
        {
            "key": "smith-a",
            "authors": "Smith, Ada",
            "year": "2020",
            "title": "Notes A",
            "paragraph": 10,
        },
        {
            "key": "smith-b",
            "authors": "Smith, Ada",
            "year": "2020",
            "title": "Notes B",
            "paragraph": 11,
        },
        {
            "key": "hopper",
            "authors": "Hopper, Grace",
            "year": "1952",
            "title": "The Education of a Computer",
            "paragraph": 12,
        },
    ]

    result = check_citation_consistency(body, references, input_type="text")

    assert result["available"] is True
    assert result["body_citation_count"] == 2
    assert {item["signature"] for item in result["missing_references"]} == {"turing:1950"}
    assert {item["signature"] for item in result["uncited_references"]} == {"hopper:1952"}
    assert result["duplicate_reference_signatures"][0]["signature"] == "smith:2020"
    assert result["duplicate_reference_signatures"][0]["count"] == 2


def test_extract_body_citations_and_no_heading_fallback():
    extracted = extract_body_citations(
        [{"text": "Prior work (Smith & Jones, 2021; see Brown, 2020) is relevant."}]
    )
    assert {item["signature"] for item in extracted["citations"]} == {
        "smith:2021",
        "brown:2020",
    }

    unavailable = check_text_citation_consistency("Only a pasted reference list without heading.")
    assert unavailable["available"] is False
    assert unavailable["body_citation_count"] == 0
