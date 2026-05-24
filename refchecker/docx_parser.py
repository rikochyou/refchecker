"""RefChecker — AI 幻觉引用与参考文献元数据核验."""
import re
import sys

from .utils import strip_latex

# --------------------------- DOCX / APA 参考文献解析 ---------------------------

def _apa_authors_to_bibtex(authors_text: str) -> str:
    """将 APA 格式作者列表转换为 BibTeX 兼容的 ' and ' 分隔格式。

    APA 格式: "Author1, A. B., Author2, C. D., & Author3, E. F."
    BibTeX 格式: "Author1, A. B. and Author2, C. D. and Author3, E. F."

    策略：按 "., " (句号-逗号-空格，作者边界) 分割，然后清理。
    """
    if not authors_text:
        return ""
    t = authors_text.strip().rstrip(',.')
    # 按 "., " 或 ". & " 或 ". and " 分割（APA 作者边界）
    parts = re.split(r'\.\s*[,，]\s*|\.\s*&\s*|\.\s+and\s+', t, flags=re.I)
    result = []
    for part in parts:
        part = part.strip().rstrip(',.')
        if not part:
            continue
        # 去除前导 "& " / "and "
        part = re.sub(r'^(?:&|and)\s+', '', part, flags=re.I).strip()
        # 加上句号（被 split 去掉了）
        if part and not part.endswith('.'):
            part += '.'
        if part:
            result.append(part)
    return " and ".join(result)


def parse_reference_text(text: str) -> dict:
    """解析 APA 格式参考文献，提取 DOI、年份、作者、标题。"""
    original = text.strip()
    if not original:
        return {"text": "", "title": "", "authors": "", "year": "", "doi": ""}

    # 1. 提取 DOI（URL 或 bare "doi: 10.xxx" 格式）
    doi = ""
    doi_val = None
    doi_start = None
    for pat, doi_group in [
        (r'https?://(dx\.)?doi\.org/(10\.\S+)', 2),
        (r'\b[dD][oO][iI]\s*:\s*(10\.\S+)', 1),
    ]:
        m = re.search(pat, original)
        if m:
            doi_val = m.group(doi_group)
            doi_start = m.start()
            break
    if doi_val:
        doi = doi_val.rstrip('.;,')
        text_body = original[:doi_start].strip().rstrip('.').strip()
    else:
        text_body = original

    if not text_body:
        text_body = original

    # 2. 提取年份: (YYYY)
    year = ""
    year_match = re.search(r'\((\d{4})\)', text_body)
    if year_match:
        year = year_match.group(1)
        authors_raw = text_body[:year_match.start()].strip().rstrip(',. (')
        authors = _apa_authors_to_bibtex(authors_raw)
        # rest = 年份之后的部分
        after_year = text_body[year_match.end():].strip()
        # 去除 "). " / ") " / ". " 前缀
        if after_year.startswith(').'):
            after_year = after_year[2:].strip()
        elif after_year.startswith(') '):
            after_year = after_year[2:].strip()
        if after_year.startswith('.'):
            after_year = after_year[1:].strip()
        after_year = after_year.strip()
    else:
        authors = ""
        after_year = ""

    # 3. 提取标题，去除尾部期刊/arXiv 信息
    title = after_year
    if after_year:
        # 去掉末尾的 arXiv ID (e.g. "arXiv:2605.12241" or "arXiv:2605.12241v1")
        title = re.sub(r'\.?\s*arXiv:\d+\.\d+(?:v\d+)?\.?\s*$', '', title).strip()

        # 尝试多种期刊边界模式，取最早匹配的位置
        journal_boundary = None
        for pat in [
            r',\s*\d+\s*\(\d+\)',           # ", 10(2)"  卷号(期号)
            r',\s*\d+,\s*\d+',              # ", 5, 134" 卷号, 页码
            r',\s*\d+,\s*\d+[–\-]\d+',      # ", 5, 134–140" 卷号, 页码范围
        ]:
            m = re.search(pat, title)
            if m and (journal_boundary is None or m.start() < journal_boundary):
                journal_boundary = m.start()

        if journal_boundary is not None:
            # 从卷号/页码边界往前找标题-期刊分隔点
            # "Title here. Journal Name, Vol, Pages" → 找最后一个 ". CapitalLetter" 分界
            prefix = title[:journal_boundary]
            matches = list(re.finditer(r'\.\s+(?=[A-Z])', prefix))
            if matches:
                cut = matches[-1].start()
                title_candidate = prefix[:cut].strip().rstrip('.')
            else:
                title_candidate = prefix.strip().rstrip('.')
            if len(title_candidate) > 5:
                title = title_candidate
        else:
            # 没有卷号/页码时，去掉末尾 "Journal Name." 模式
            # 支持内部大写（NeuroImage）和多词期刊名（Nature Reviews Neuroscience）
            matches = list(re.finditer(r'\.\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\.?\s*$', title))
            if matches:
                m = matches[-1]
                if m.start() > 0:
                    title_candidate = title[:m.start()].strip().rstrip('.')
                    if len(title_candidate) > 5:
                        title = title_candidate

    return {
        "text": original,
        "title": title or original,
        "authors": authors,
        "year": year,
        "doi": doi,
    }


def parse_text_references(text: str) -> list[dict]:
    """解析纯文本中的多条参考文献。

    优先按空行分割；若只有一条则按单换行分割
    （适配从 AI/网页直接复制的逐行引用格式）。
    """
    trimmed = text.strip()
    blocks = re.split(r'\n\s*\n', trimmed)
    if len(blocks) <= 1:
        blocks = [b.strip() for b in trimmed.split('\n') if b.strip()]
    refs = []
    for i, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue
        parsed = parse_reference_text(block)
        parsed["index"] = i
        parsed["paragraph"] = i + 1
        refs.append(parsed)
    return refs


def extract_references_from_docx(path: str) -> list[dict]:
    """从 Word 文档中提取参考文献段落。

    识别所有 "Bibliography" 样式的段落，
    返回包含原始文本和解析元数据的字典列表。
    """
    try:
        from docx import Document as DocxDocument
    except ImportError:
        sys.exit("请先安装 python-docx: pip install python-docx")

    doc = DocxDocument(path)
    refs = []
    for i, para in enumerate(doc.paragraphs):
        style = (para.style.name if para.style else "").lower()
        text = para.text.strip()
        if not text:
            continue
        # "Bibliography" 样式 或 "参考" / "参考文献" 样式
        is_bib = "bibliography" in style or "reference" in style or "biblio" in style
        if not is_bib:
            # 没有样式信息时，检查是否像参考文献格式
            # APA 格式特征: 包含 "(19xx)" 或 "(20xx)" 且有 DOI
            has_year = bool(re.search(r'\((?:19|20)\d{2}\)', text))
            has_doi = bool(re.search(r'doi\.org/', text))
            if not (has_year and has_doi):
                continue

        parsed = parse_reference_text(text)
        parsed["index"] = i  # 段落序号
        parsed["paragraph"] = i + 1  # 1-based for display
        refs.append(parsed)

    return refs
