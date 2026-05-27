"""RefChecker — 疑似虚构引用与参考文献元数据核验."""
import re
from difflib import SequenceMatcher

from .utils import strip_latex, normalize_ascii, NAME_PARTICLES, NAME_SUFFIXES, title_similarity, extract_year, clean_doi

def parse_author_name(raw: str = "", given: str = "", family: str = "") -> dict:
    """将作者名解析成 given / family / initials / normalized forms。"""
    raw = strip_latex(raw or "")
    given = strip_latex(given or "")
    family = strip_latex(family or "")

    if not (given or family):
        if "," in raw:
            parts = [p.strip() for p in raw.split(",")]
            family = parts[0]
            given = " ".join(parts[1:]).strip()
        else:
            tokens = raw.split()
            while tokens and normalize_ascii(tokens[-1]) in NAME_SUFFIXES:
                tokens.pop()
            if len(tokens) == 1:
                family = tokens[0] if tokens else ""
                given = ""
            elif len(tokens) > 1:
                # 粗略处理 van der Waals / de Souza 之类姓氏粒子
                family_tokens = [tokens[-1]]
                idx = len(tokens) - 2
                while idx >= 0 and normalize_ascii(tokens[idx]) in NAME_PARTICLES:
                    family_tokens.insert(0, tokens[idx])
                    idx -= 1
                family = " ".join(family_tokens)
                given = " ".join(tokens[: idx + 1])

    family_tokens = family.split()
    while family_tokens and normalize_ascii(family_tokens[-1]) in NAME_SUFFIXES:
        family_tokens.pop()
    family = " ".join(family_tokens)

    given_norm = normalize_ascii(given)
    family_norm = normalize_ascii(family)
    full = " ".join(part for part in [given, family] if part).strip() or raw
    full_norm = normalize_ascii(full)
    initials = "".join(token[0] for token in given_norm.split() if token)

    return {
        "raw": raw or full,
        "given": given,
        "family": family,
        "given_norm": given_norm,
        "family_norm": family_norm,
        "full_norm": full_norm,
        "initials": initials,
        "display": full,
    }


def split_bibtex_author_field(author_field: str) -> tuple[list[dict], bool]:
    """
    解析 BibTeX author 字段。

    返回:
        authors: 作者列表
        truncated: 是否使用 others / et al. 表示省略
    """
    if not author_field:
        return [], False

    text = str(author_field).replace("\n", " ").replace("\r", " ")
    text = normalize_author_field(text)
    parts = [p.strip() for p in re.split(r"\s+and\s+", text) if p.strip()]

    authors = []
    truncated = False
    for part in parts:
        clean = strip_latex(part).strip()
        if re.fullmatch(r"(?i)(others|et\.?\s*al\.?)", clean):
            truncated = True
            continue
        authors.append(parse_author_name(clean))
    return authors, truncated


def normalize_author_field(author_field: str) -> str:
    """Normalize common author-list formats into BibTeX-compatible ``and`` lists.

    Downstream comparison intentionally expects BibTeX-style author separators.
    LLMs and pasted APA references often return authors as
    ``Last, A., Last, B., & Last, C.``.  Without normalization that whole string
    is treated as one ``Last, given`` author, so author counts become 1.
    """
    text = str(author_field or "").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip().rstrip(",;")
    if not text:
        return ""

    if re.search(r"\s+and\s+", text, flags=re.I):
        return text

    if ";" in text:
        parts = [p.strip() for p in text.split(";") if p.strip()]
        if len(parts) > 1:
            return " and ".join(parts)

    # APA-style author list, e.g.
    # "Vaswani, A., Shazeer, N., ... Kaiser, L., & Polosukhin, I."
    apa_parts = [
        p.strip().rstrip(",")
        for p in re.split(r"\.\s*[,，]\s*|\.\s*&\s*|\.\s+and\s+", text, flags=re.I)
        if p.strip().rstrip(",")
    ]
    if len(apa_parts) > 1:
        normalized = []
        for part in apa_parts:
            part = re.sub(r"^(?:&|and)\s+", "", part, flags=re.I).strip().rstrip(",")
            if part and not part.endswith("."):
                part += "."
            if part:
                normalized.append(part)
        if len(normalized) > 1:
            return " and ".join(normalized)

    return text


def first_author_lastname(author_field: str) -> str:
    """从 BibTeX author 字段抽出第一作者的姓，用于辅助检索。"""
    authors, _ = split_bibtex_author_field(author_field)
    return authors[0]["family"] if authors else ""


def author_display_list(authors: list[dict], limit: int | None = None) -> str:
    selected = authors if limit is None else authors[:limit]
    names = [a.get("display") or a.get("raw") or "" for a in selected]
    names = [n for n in names if n]
    text = "; ".join(names)
    if limit is not None and len(authors) > limit:
        text += f"; ... (+{len(authors) - limit})"
    return text


def family_matches(a: dict, b: dict) -> bool:
    af = a.get("family_norm", "")
    bf = b.get("family_norm", "")
    if not af or not bf:
        return False
    if af == bf:
        return True
    af_tokens = af.split()
    bf_tokens = bf.split()
    # 数据源有时只保留复合姓氏的最后一段，例如 "Mohammadzadeh Asl" vs "Asl"。
    if af_tokens and bf_tokens and af_tokens[-1] == bf_tokens[-1]:
        if len(af_tokens) > 1 or len(bf_tokens) > 1:
            return True
    if len(af) >= 5 and len(bf) >= 5 and (af in bf or bf in af):
        return True
    return SequenceMatcher(None, af, bf).ratio() >= 0.88


def initials_compatible(a: dict, b: dict) -> bool:
    ai = a.get("initials", "")
    bi = b.get("initials", "")
    # 数据库或 BibTeX 只有姓氏时，不因缺少名缩写直接判错
    if not ai or not bi:
        return True
    return ai.startswith(bi) or bi.startswith(ai)


def author_matches(a: dict, b: dict) -> bool:
    return family_matches(a, b) and initials_compatible(a, b)


def match_indices(left: list[dict], right: list[dict]) -> set[int]:
    matched_right = set()
    for a in left:
        for j, b in enumerate(right):
            if j in matched_right:
                continue
            if author_matches(a, b):
                matched_right.add(j)
                break
    return matched_right


def compare_author_lists(bib_author_field: str, db_authors: list[dict]) -> dict:
    """比较 BibTeX 作者列表与数据库作者列表。"""
    bib_authors, bib_truncated = split_bibtex_author_field(bib_author_field)

    if not bib_authors:
        return {
            "status": "unknown",
            "reason": "BibTeX 缺少 author 字段，无法核查作者",
            "bib_author_count": 0,
            "matched_author_count": len(db_authors),
            "bib_authors": "",
            "matched_authors": author_display_list(db_authors),
            "missing_authors": "",
            "extra_authors": "",
            "order_mismatch": False,
            "first_author_match": "",
        }

    if not db_authors:
        return {
            "status": "unknown",
            "reason": "数据库返回记录缺少作者元数据，无法核查作者",
            "bib_author_count": len(bib_authors),
            "matched_author_count": 0,
            "bib_authors": author_display_list(bib_authors),
            "matched_authors": "",
            "missing_authors": "",
            "extra_authors": "",
            "order_mismatch": False,
            "first_author_match": "",
        }

    first_ok = author_matches(bib_authors[0], db_authors[0])
    ordered_prefix_ok = all(
        author_matches(bib_authors[i], db_authors[i])
        for i in range(min(len(bib_authors), len(db_authors)))
    )
    exact_order_ok = (
        len(bib_authors) == len(db_authors)
        and all(author_matches(bib_authors[i], db_authors[i]) for i in range(len(bib_authors)))
    )

    matched_db_indices = match_indices(bib_authors, db_authors)
    matched_bib_indices = match_indices(db_authors, bib_authors)

    missing_authors = [
        db_authors[i] for i in range(len(db_authors)) if i not in matched_db_indices
    ]
    extra_authors = [
        bib_authors[i] for i in range(len(bib_authors)) if i not in matched_bib_indices
    ]

    same_author_set = not missing_authors and not extra_authors
    order_mismatch = same_author_set and not exact_order_ok

    if exact_order_ok:
        status = "exact"
        reason = "作者数量、顺序与姓名基本一致"
    elif bib_truncated and ordered_prefix_ok and len(bib_authors) <= len(db_authors):
        status = "partial"
        reason = (
            f"BibTeX 使用 others/et al. 省略作者；前 {len(bib_authors)} 位作者与数据库一致，"
            f"数据库共 {len(db_authors)} 位作者"
        )
        # 这种情况下缺少的作者是预期省略，不视为可疑
        missing_authors = []
    elif not first_ok:
        status = "mismatch"
        reason = (
            "第一作者不一致："
            f"BibTeX 为 {bib_authors[0].get('display', '')}，"
            f"数据库为 {db_authors[0].get('display', '')}"
        )
    elif order_mismatch:
        status = "mismatch"
        reason = "作者集合基本相同，但作者顺序与数据库不一致"
    elif missing_authors or extra_authors:
        status = "mismatch"
        bits = []
        if len(bib_authors) != len(db_authors):
            bits.append(f"作者数量不一致：BibTeX {len(bib_authors)} 位，数据库 {len(db_authors)} 位")
        if missing_authors:
            bits.append("BibTeX 可能省略: " + author_display_list(missing_authors, limit=5))
        if extra_authors:
            bits.append("BibTeX 可能额外/可疑: " + author_display_list(extra_authors, limit=5))
        reason = "；".join(bits)
    else:
        status = "partial"
        reason = "作者姓名存在格式差异，建议抽查"

    return {
        "status": status,
        "reason": reason,
        "bib_author_count": len(bib_authors),
        "matched_author_count": len(db_authors),
        "bib_authors": author_display_list(bib_authors),
        "matched_authors": author_display_list(db_authors),
        "missing_authors": author_display_list(missing_authors),
        "extra_authors": author_display_list(extra_authors),
        "order_mismatch": order_mismatch,
        "first_author_match": "Yes" if first_ok else "No",
    }


def candidate_score(candidate: dict, bib_author: str = "", bib_year: str = "") -> float:
    """
    给候选结果打分。

    标题相似度仍是主指标；当多个候选标题完全相同时，优先选择年份和作者更一致的记录。
    这能减少 CrossRef 中同题转载、预印本、书籍条目把原始论文“挤掉”的情况。
    """
    score = candidate.get("similarity", 0.0)

    by = extract_year(bib_year)
    my = extract_year(candidate.get("year", ""))
    if by and my:
        diff = abs(int(by) - int(my))
        if diff == 0:
            score += 0.08
        elif diff == 1:
            score -= 0.015
        elif diff <= 3:
            score -= 0.04
        else:
            score -= 0.08

    if bib_author and candidate.get("author_list"):
        author_check = compare_author_lists(bib_author, candidate.get("author_list", []))
        if author_check["status"] == "exact":
            score += 0.05
        elif author_check["status"] == "partial":
            score += 0.02
        elif author_check["status"] == "mismatch":
            score -= 0.04
            if author_check.get("first_author_match") == "No":
                score -= 0.06

    if candidate.get("doi"):
        score += 0.005

    return score

