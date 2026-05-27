from refchecker.docx_parser import parse_text_references
from refchecker.author import split_bibtex_author_field
from refchecker.llm_parser import apply_llm_parsing, reference_needs_llm_parse


def test_llm_auto_parsing_merges_extracted_fields(monkeypatch):
    refs = parse_text_references(
        "1. Smith J, Brown A. A precise paper title from a numbered citation. Nature. 2020. doi:10.1234/demo"
    )
    assert reference_needs_llm_parse(refs[0]) is True

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"references":[{"input_index":0,'
                                '"title":"A precise paper title from a numbered citation",'
                                '"authors":"Smith, J. and Brown, A.",'
                                '"year":"2020",'
                                '"doi":"10.1234/demo",'
                                '"url":"",'
                                '"confidence":0.91}]}'
                            )
                        }
                    }
                ]
            }

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("refchecker.llm_parser.requests.post", fake_post)
    parsed = apply_llm_parsing(
        refs,
        llm_parse_mode="auto",
        llm_api_key="test-key",
        llm_model="test-model",
        llm_base_url="https://llm.example/v1",
    )

    assert calls[0]["url"] == "https://llm.example/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["json"]["model"] == "test-model"
    assert parsed[0]["parser"] == "llm"
    assert parsed[0]["title"] == "A precise paper title from a numbered citation"
    assert parsed[0]["authors"] == "Smith, J. and Brown, A."
    assert parsed[0]["year"] == "2020"
    assert parsed[0]["doi"] == "10.1234/demo"


def test_llm_auto_without_api_key_keeps_rules_and_warns():
    refs = parse_text_references("1. Smith J. Ambiguous title. Journal. 2020.")
    parsed = apply_llm_parsing(refs, llm_parse_mode="auto", llm_api_key="")
    assert parsed[0]["parser"] == "rules"
    assert "not configured" in parsed[0]["parser_warning"]


def test_llm_auto_is_llm_first_even_when_rule_parse_looks_ok(monkeypatch):
    refs = parse_text_references(
        "Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). "
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. "
        "Proceedings of NAACL-HLT, 4171-4186. https://doi.org/10.18653/v1/N19-1423"
    )
    assert reference_needs_llm_parse(refs[0]) is False

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"references":[{"input_index":0,'
                                '"title":"BERT title from LLM",'
                                '"authors":"Devlin, J. and Chang, M.-W. and Lee, K. and Toutanova, K.",'
                                '"year":"2019",'
                                '"doi":"10.18653/v1/N19-1423",'
                                '"url":"https://doi.org/10.18653/v1/N19-1423",'
                                '"confidence":0.95}]}'
                            )
                        }
                    }
                ]
            }

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return FakeResponse()

    monkeypatch.setattr("refchecker.llm_parser.requests.post", fake_post)
    parsed = apply_llm_parsing(refs, llm_parse_mode="auto", llm_api_key="test-key")

    assert len(calls) == 1
    assert parsed[0]["parser"] == "llm"
    assert parsed[0]["title"] == "BERT title from LLM"


def test_llm_falls_back_to_rule_fields_when_llm_returns_no_usable_fields(monkeypatch):
    refs = parse_text_references(
        "Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). "
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. "
        "Proceedings of NAACL-HLT, 4171-4186. https://doi.org/10.18653/v1/N19-1423"
    )
    rule_title = refs[0]["title"]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"references":[{"input_index":0,'
                                '"title":"",'
                                '"authors":"",'
                                '"year":"",'
                                '"doi":"",'
                                '"url":"",'
                                '"confidence":0.1,'
                                '"warning":"unable to parse"}]}'
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("refchecker.llm_parser.requests.post", lambda *args, **kwargs: FakeResponse())
    parsed = apply_llm_parsing(refs, llm_parse_mode="always", llm_api_key="test-key")

    assert parsed[0]["parser"] == "rules"
    assert parsed[0]["title"] == rule_title
    assert "no usable fields" in parsed[0]["parser_note"]
    assert parsed[0]["parser_warning"] == "unable to parse"


def test_llm_apa_author_string_is_normalized_to_multiple_authors(monkeypatch):
    refs = parse_text_references(
        "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., "
        "Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). "
        "Attention is All You Need. Advances in Neural Information Processing Systems, 30. "
        "https://arxiv.org/abs/1706.03762"
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"references":[{"input_index":0,'
                                '"citation_style":"apa",'
                                '"title":"Attention is All You Need",'
                                '"authors":["Vaswani, A.","Shazeer, N.","Parmar, N.","Uszkoreit, J.","Jones, L.",{"family":"Gomez","given":"A. N."},"Kaiser, L.","Polosukhin, I."],'
                                '"year":"2017",'
                                '"doi":"",'
                                '"url":"https://arxiv.org/abs/1706.03762",'
                                '"confidence":0.96}]}'
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr("refchecker.llm_parser.requests.post", lambda *args, **kwargs: FakeResponse())
    parsed = apply_llm_parsing(refs, llm_parse_mode="auto", llm_api_key="test-key")
    authors, truncated = split_bibtex_author_field(parsed[0]["authors"])

    assert parsed[0]["parser"] == "llm"
    assert parsed[0]["parser_citation_style"] == "apa"
    assert "detected style: apa" in parsed[0]["parser_note"]
    assert truncated is False
    assert len(authors) == 8
    assert authors[0]["family"] == "Vaswani"
    assert authors[-1]["family"] == "Polosukhin"
