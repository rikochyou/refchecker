"""正文引用与参考文献列表一致性检查。

该模块只做本地、规则驱动的结构化检查，不调用大语言模型。
目标是发现常见的文档级问题：

- 正文出现了 “Smith, 2020”，但参考文献列表没有 Smith 2020；
- 参考文献列表有某条文献，但正文没有引用；
- 同一年同一第一作者的参考文献重复出现，可能需要人工区分 2020a/2020b；
- 部分正文引用或参考文献无法解析，提示人工核查。

说明：这里的签名采用 “第一作者姓 + 年份” 的保守规则，仅用于筛查，不是最终学术裁决。
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from typing import Any

from .author import first_author_lastname, parse_author_name
from .docx_parser import parse_reference_text, parse_text_references
from .utils import normalize_ascii, truncate


REFERENCE_HEADING_RE = re.compile(
    r"^\s*(references|bibliography|works\s+cited|literature\s+cited|参考文献|参考资料)\s*$",
    re.I,
)


def not_available(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "body_citation_count": 0,
        "body_signature_count": 0,
        "reference_signature_count": 0,
        "missing_references": [],
        "uncited_references": [],
        "duplicate_reference_signatures": [],
        "unparsed_body_citations": [],
        "unparsed_references": [],
    }


def _is_reference_style(style_name: str) -> bool:
    style = (style_name or "").lower()
    return "bibliography" in style or "reference" in style or "biblio" in style


def _is_reference_heading(text: str) -> bool:
    return bool(REFERENCE_HEADING_RE.match(text or ""))


def split_docx_body_and_references(path: str) -> dict[str, Any]:
    """将 DOCX 粗略分为正文段落与参考文献段落。"""
    try:
        from docx import Document as DocxDocument
    except ImportError:
        sys.exit("请先安装 python-docx: pip install python-docx")

    doc = DocxDocument(path)
    body: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    in_references = False
    first_reference_paragraph: int | None = None

    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        style = para.style.name if para.style else ""
        is_bib_style = _is_reference_style(style)
        if _is_reference_heading(text):
            in_references = True
            if first_reference_paragraph is None:
                first_reference_paragraph = i + 1
            continue
        if is_bib_style:
            in_references = True
            if first_reference_paragraph is None:
                first_reference_paragraph = i + 1

        item = {"text": text, "paragraph": i + 1, "style": style}
        if in_references:
            references.append(item)
        else:
            body.append(item)

    return {
        "body": body,
        "references": references,
        "has_reference_section": bool(references),
        "first_reference_paragraph": first_reference_paragraph,
    }


def split_text_body_and_references(text: str) -> dict[str, Any]:
    """识别纯文本中的参考文献标题，并切分正文/参考文献列表。

    若未发现 “References / Bibliography / 参考文献” 标题，则认为用户粘贴的是参考文献列表，
    不进行正文一致性检查。
    """
    paragraphs = [
        {"text": p.strip(), "paragraph": i + 1}
        for i, p in enumerate(re.split(r"\n\s*\n|\r?\n", text.strip()))
        if p.strip()
    ]
    heading_index: int | None = None
    for i, item in enumerate(paragraphs):
        if _is_reference_heading(item["text"]):
            heading_index = i
            break

    if heading_index is None:
        return {
            "body": [],
            "references": [],
            "has_reference_section": False,
            "reference_text": text,
        }

    body = paragraphs[:heading_index]
    ref_items = paragraphs[heading_index + 1 :]
    reference_text = "\n\n".join(item["text"] for item in ref_items)
    refs = parse_text_references(reference_text)
    for ref, item in zip(refs, ref_items):
        ref["paragraph"] = item["paragraph"]
    return {
        "body": body,
        "references": refs,
        "has_reference_section": True,
        "reference_text": reference_text,
    }


def _signature_from_family_year(family: str, year: str) -> str:
    year_match = re.search(r"(?:19|20)\d{2}", year or "")
    year_base = year_match.group(0) if year_match else ""
    family_norm = normalize_ascii(family or "")
    if not family_norm or not year_base:
        return ""
    return f"{family_norm}:{year_base}"


def _display_from_signature(family: str, year: str) -> str:
    year_match = re.search(r"(?:19|20)\d{2}[a-z]?", year or "", re.I)
    return f"{family.strip()} {year_match.group(0) if year_match else year}".strip()


def _first_author_from_citation_text(authors_text: str) -> str:
    text = authors_text.strip()
    text = re.sub(r"^(?:see|e\.g\.|eg|cf\.|also|例如|参见)\s+", "", text, flags=re.I)
    text = re.sub(r"\bet\s+al\.?\s*$", "", text, flags=re.I).strip()
    # “Smith & Jones” / “Smith and Jones” / “Smith, Jones, & Brown” 取第一作者。
    text = re.split(r"\s+(?:and|&)\s+|[,，]", text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r"[^\w\s'\-’\u4e00-\u9fff]", " ", text, flags=re.UNICODE).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    parsed = parse_author_name(text)
    return parsed.get("family") or text.split()[-1]


def _add_body_citation(
    citations: list[dict[str, Any]],
    unparsed: list[str],
    authors_text: str,
    year: str,
    context: str,
    paragraph: int | None = None,
) -> None:
    family = _first_author_from_citation_text(authors_text)
    signature = _signature_from_family_year(family, year)
    if not signature:
        raw = f"{authors_text} {year}".strip()
        if raw:
            unparsed.append(raw)
        return
    citations.append(
        {
            "signature": signature,
            "family": family,
            "year": re.search(r"(?:19|20)\d{2}[a-z]?", year, re.I).group(0),
            "display": _display_from_signature(family, year),
            "context": truncate(context, 220),
            "paragraph": paragraph,
        }
    )


def extract_body_citations(paragraphs: list[dict[str, Any]]) -> dict[str, Any]:
    """提取正文中的 APA 风格作者-年份引用签名。"""
    citations: list[dict[str, Any]] = []
    unparsed: list[str] = []

    # Parenthetical: (Smith, 2020; Jones & Brown, 2021)
    parenthetical_re = re.compile(r"\(([^()]{1,320}?(?:19|20)\d{2}[a-z]?[^()]*)\)")
    # Narrative: Smith (2020), Smith et al. (2020), Smith and Jones (2020)
    narrative_re = re.compile(
        r"\b([A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+(?:\s+et\s+al\.|\s+(?:and|&)\s+"
        r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’\-]+)?)\s*\(((?:19|20)\d{2}[a-z]?)\)",
        re.I,
    )

    for item in paragraphs:
        text = item.get("text", "")
        paragraph = item.get("paragraph")
        for match in parenthetical_re.finditer(text):
            content = match.group(1)
            for segment in re.split(r";|；", content):
                year_match = re.search(r"((?:19|20)\d{2}[a-z]?)", segment, re.I)
                if not year_match:
                    continue
                authors_text = segment[: year_match.start()].strip(" ,，;；")
                if not authors_text:
                    continue
                _add_body_citation(citations, unparsed, authors_text, year_match.group(1), text, paragraph)
        for match in narrative_re.finditer(text):
            _add_body_citation(citations, unparsed, match.group(1), match.group(2), text, paragraph)

    return {"citations": citations, "unparsed": sorted(set(unparsed))}


def _reference_signature(ref: dict[str, Any]) -> dict[str, Any]:
    authors = ref.get("authors", "")
    family = first_author_lastname(authors)
    year = ref.get("year", "")
    if not family or not year:
        parsed = parse_reference_text(ref.get("text", ""))
        family = first_author_lastname(parsed.get("authors", "")) or family
        year = parsed.get("year", "") or year
    signature = _signature_from_family_year(family, year)
    return {
        "signature": signature,
        "family": family,
        "year": year,
        "display": _display_from_signature(family, year) if signature else "",
        "title": ref.get("title", "") or parse_reference_text(ref.get("text", "")).get("title", ""),
        "paragraph": ref.get("paragraph"),
        "key": ref.get("key") or f"ref[{ref.get('paragraph', ref.get('index', '?'))}]",
    }


def check_citation_consistency(
    body_paragraphs: list[dict[str, Any]],
    references: list[dict[str, Any]],
    *,
    input_type: str,
) -> dict[str, Any]:
    if not body_paragraphs:
        return not_available("未识别到可检查的正文段落；仅对 DOCX 或包含参考文献标题的 TXT 做正文一致性检查。")
    if not references:
        return not_available("未识别到参考文献列表。")

    body = extract_body_citations(body_paragraphs)
    body_citations = body["citations"]
    body_counter = Counter(item["signature"] for item in body_citations if item["signature"])
    body_examples: dict[str, dict[str, Any]] = {}
    for item in body_citations:
        body_examples.setdefault(item["signature"], item)

    reference_items = [_reference_signature(ref) for ref in references]
    reference_by_sig: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unparsed_refs: list[dict[str, Any]] = []
    for item in reference_items:
        if item["signature"]:
            reference_by_sig[item["signature"]].append(item)
        else:
            unparsed_refs.append(item)

    missing = []
    for signature, count in sorted(body_counter.items()):
        if signature not in reference_by_sig:
            example = body_examples[signature]
            missing.append(
                {
                    "signature": signature,
                    "citation": example["display"],
                    "count": count,
                    "paragraph": example.get("paragraph"),
                    "context": example.get("context", ""),
                }
            )

    uncited = []
    for signature, refs in sorted(reference_by_sig.items()):
        if signature not in body_counter:
            for ref in refs:
                uncited.append(
                    {
                        "signature": signature,
                        "citation": ref["display"],
                        "key": ref["key"],
                        "title": ref["title"],
                        "paragraph": ref.get("paragraph"),
                    }
                )

    duplicates = []
    for signature, refs in sorted(reference_by_sig.items()):
        if len(refs) > 1:
            duplicates.append(
                {
                    "signature": signature,
                    "citation": refs[0]["display"],
                    "count": len(refs),
                    "items": [
                        {
                            "key": ref["key"],
                            "title": ref["title"],
                            "paragraph": ref.get("paragraph"),
                        }
                        for ref in refs
                    ],
                }
            )

    return {
        "available": True,
        "input_type": input_type,
        "body_citation_count": sum(body_counter.values()),
        "body_signature_count": len(body_counter),
        "reference_signature_count": len(reference_by_sig),
        "missing_references": missing,
        "uncited_references": uncited,
        "duplicate_reference_signatures": duplicates,
        "unparsed_body_citations": body["unparsed"][:50],
        "unparsed_references": unparsed_refs[:50],
        "method": "本地规则：提取正文 APA 作者-年份引用，并用第一作者姓 + 年份与参考文献列表比对。",
        "disclaimer": "该检查用于筛查遗漏或未引用条目；同作者同年份、脚注体例、编号体例和复杂引用需人工确认。",
    }


def check_docx_citation_consistency(path: str, references: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    split = split_docx_body_and_references(path)
    refs = references if references is not None else [
        {**parse_reference_text(item["text"]), "paragraph": item["paragraph"]}
        for item in split["references"]
    ]
    return check_citation_consistency(split["body"], refs, input_type="docx")


def check_text_citation_consistency(
    text: str,
    references: list[dict[str, Any]] | None = None,
    parsed_split: dict[str, Any] | None = None,
) -> dict[str, Any]:
    split = parsed_split or split_text_body_and_references(text)
    if not split.get("has_reference_section"):
        return not_available("未识别到 References / 参考文献 标题；纯参考文献列表不做正文一致性检查。")
    refs = references if references is not None else split.get("references", [])
    return check_citation_consistency(split.get("body", []), refs, input_type="text")

