from refchecker.author import (
    candidate_score,
    compare_author_lists,
    first_author_lastname,
    normalize_author_field,
    parse_author_name,
    split_bibtex_author_field,
)
from refchecker.utils import (
    clean_doi,
    compare_doi,
    compare_year,
    extract_year,
    normalize_ascii,
    strip_latex,
    title_similarity,
    truncate,
)


def test_text_normalization_and_metadata_comparators():
    assert strip_latex(r"{\emph{Deep}} Learning --- G{\"o}del") == "Deep Learning --- Godel"
    assert normalize_ascii("Café-au-lait, Version 2!") == "cafe au lait version 2"
    assert title_similarity("A Robust Test", "A robust test") == 1.0
    assert extract_year("published online 2024-05-01") == "2024"
    assert clean_doi(" https://doi.org/10.1000/ABC. ") == "10.1000/abc"
    assert truncate("abcdef", 4) == "abcd..."

    assert compare_year("2024", "2024-01")["status"] == "exact"
    assert compare_year("", "2024")["status"] == "unknown"
    assert compare_year("2024", "2023")["status"] == "mismatch"

    assert compare_doi("doi:10.1000/ABC", "https://doi.org/10.1000/abc")["status"] == "exact"
    assert compare_doi("", "10.1000/abc")["status"] == "missing_in_bib"
    assert compare_doi("10.1000/a", "10.1000/b")["status"] == "mismatch"


def test_author_parsing_particles_suffixes_and_truncation():
    assert parse_author_name("Ada Lovelace")["family"] == "Lovelace"
    assert parse_author_name("Lovelace, Ada")["given"] == "Ada"
    assert parse_author_name("Ludwig van Beethoven Jr.")["family"] == "van Beethoven"
    assert first_author_lastname("Lovelace, Ada and Turing, Alan") == "Lovelace"

    authors, truncated = split_bibtex_author_field(
        "Lovelace, Ada and Turing, Alan and others"
    )
    assert [a["family"] for a in authors] == ["Lovelace", "Turing"]
    assert truncated is True


def test_author_parsing_normalizes_apa_comma_list_from_llm():
    field = (
        "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., "
        "Gomez, A. N., Kaiser, L., & Polosukhin, I."
    )
    normalized = normalize_author_field(field)
    authors, truncated = split_bibtex_author_field(field)

    assert truncated is False
    assert normalized.startswith("Vaswani, A. and Shazeer, N.")
    assert [a["family"] for a in authors] == [
        "Vaswani",
        "Shazeer",
        "Parmar",
        "Uszkoreit",
        "Jones",
        "Gomez",
        "Kaiser",
        "Polosukhin",
    ]


def test_author_list_comparison_exact_partial_order_and_mismatch():
    db_authors = [
        parse_author_name(given="Ada", family="Lovelace"),
        parse_author_name(given="Alan", family="Turing"),
        parse_author_name(given="Grace", family="Hopper"),
    ]

    exact = compare_author_lists(
        "Lovelace, Ada and Turing, Alan and Hopper, Grace",
        db_authors,
    )
    assert exact["status"] == "exact"
    assert exact["first_author_match"] == "Yes"

    partial = compare_author_lists("Lovelace, Ada and others", db_authors)
    assert partial["status"] == "partial"
    assert partial["missing_authors"] == ""

    order = compare_author_lists(
        "Lovelace, Ada and Hopper, Grace and Turing, Alan",
        db_authors,
    )
    assert order["status"] == "mismatch"
    assert order["order_mismatch"] is True
    assert order["first_author_match"] == "Yes"

    mismatch = compare_author_lists("Curie, Marie", db_authors)
    assert mismatch["status"] == "mismatch"
    assert mismatch["first_author_match"] == "No"


def test_candidate_score_rewards_consistent_metadata_and_penalizes_bad_first_author():
    good = {
        "similarity": 0.9,
        "year": "1843",
        "author_list": [parse_author_name(given="Ada", family="Lovelace")],
        "doi": "10.1000/good",
    }
    bad = {
        "similarity": 0.9,
        "year": "2024",
        "author_list": [parse_author_name(given="Alan", family="Turing")],
    }
    assert candidate_score(good, "Lovelace, Ada", "1843") > candidate_score(
        bad, "Lovelace, Ada", "1843"
    )
