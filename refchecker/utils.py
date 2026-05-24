"""RefChecker — AI 幻觉引用与参考文献元数据核验."""
import re
import unicodedata
from difflib import SequenceMatcher

NAME_PARTICLES = {
    "da", "de", "del", "della", "der", "di", "dos", "du",
    "la", "le", "van", "von", "den", "ten", "ter",
}

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def strip_latex(text: str) -> str:
    """粗略去除常见 BibTeX/LaTeX 标记，保留可比较文本。"""
    if not text:
        return ""
    t = str(text).replace("\n", " ").replace("\r", " ")
    # 将 \emph{abc} 之类替换为 abc；对嵌套命令不做复杂解析
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", t)
    # 处理常见 LaTeX 重音写法，如 {\"o} / \'e
    t = re.sub(r"\\['`\"^~=.uvHtcdbk]\s*\{?([A-Za-z])\}?", r"\1", t)
    t = re.sub(r"\\[a-zA-Z]+", " ", t)
    t = t.replace("{", "").replace("}", "").replace("~", " ")
    return " ".join(t.split())


def normalize_ascii(text: str) -> str:
    """转小写、去重音、去标点，得到便于相似度比较的文本。"""
    t = strip_latex(text)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s-]", " ", t)
    t = t.replace("-", " ")
    return " ".join(t.split())


def normalize_title(title: str) -> str:
    return normalize_ascii(title)


def title_similarity(t1: str, t2: str) -> float:
    return SequenceMatcher(None, normalize_title(t1), normalize_title(t2)).ratio()


def extract_year(value) -> str:
    """从 BibTeX 年份字段或数据库年份字段中提取 4 位年份。"""
    if value is None:
        return ""
    m = re.search(r"(18|19|20|21)\d{2}", str(value))
    return m.group(0) if m else ""


def clean_doi(doi: str) -> str:
    """规范化 DOI，去除 URL 前缀、doi: 前缀和多余标点。"""
    if not doi:
        return ""
    d = strip_latex(str(doi)).strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    d = d.strip().strip(".;,")
    return d.lower()


def truncate(text: str, n: int = 80) -> str:
    text = text or ""
    return text[:n] + ("..." if len(text) > n else "")


# --------------------------- 年份 / DOI 比较 ---------------------------

def compare_year(bib_year: str, matched_year: str) -> dict:
    by = extract_year(bib_year)
    my = extract_year(matched_year)
    if not by:
        return {"status": "unknown", "reason": "BibTeX 缺少年份", "bib_year": "", "matched_year": my}
    if not my:
        return {"status": "unknown", "reason": "数据库缺少年份", "bib_year": by, "matched_year": ""}
    if by == my:
        return {"status": "exact", "reason": "年份一致", "bib_year": by, "matched_year": my}
    return {
        "status": "mismatch",
        "reason": f"年份不一致：BibTeX {by}，数据库 {my}",
        "bib_year": by,
        "matched_year": my,
    }


def compare_doi(bib_doi: str, matched_doi: str) -> dict:
    bd = clean_doi(bib_doi)
    md = clean_doi(matched_doi)
    if not bd and not md:
        return {"status": "unknown", "reason": "BibTeX 和数据库均未提供 DOI", "bib_doi": "", "matched_doi": ""}
    if not bd and md:
        return {"status": "missing_in_bib", "reason": f"BibTeX 缺少 DOI，数据库 DOI 为 {md}", "bib_doi": "", "matched_doi": md}
    if bd and not md:
        return {"status": "unknown", "reason": "BibTeX 有 DOI，但数据库结果未提供 DOI", "bib_doi": bd, "matched_doi": ""}
    if bd == md:
        return {"status": "exact", "reason": "DOI 一致", "bib_doi": bd, "matched_doi": md}
    return {
        "status": "mismatch",
        "reason": f"DOI 不一致：BibTeX {bd}，数据库 {md}",
        "bib_doi": bd,
        "matched_doi": md,
    }

