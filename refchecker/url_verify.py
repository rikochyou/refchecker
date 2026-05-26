"""RefChecker — 疑似虚构引用与参考文献元数据核验."""
import re
import time

import requests

from .utils import strip_latex, title_similarity, extract_year

# --------------------------- URL 资源验证 ---------------------------

def detect_url_platform(url: str) -> str:
    """根据 URL 域名识别平台类型。"""
    if not url:
        return "none"
    u = url.lower()
    if "huggingface.co" in u:
        return "huggingface"
    if "github.com" in u:
        return "github"
    return "general"


def _parse_author_from_org(org_name: str) -> list[dict]:
    """将组织名称（如 Meta / NVIDIA Corporation）转为 author_list 兼容格式。"""
    org = strip_latex(org_name).strip("{}").strip()
    if not org:
        return []
    return [parse_author_name(org)]


def _hf_api_headers() -> dict:
    return {"User-Agent": "RefChecker/1.2"}


def _extract_hf_path(url: str) -> tuple[str, str] | None:
    """从 HuggingFace URL 中提取 (org, repo_name)。

    支持:
        https://huggingface.co/{org}/{name}
        https://huggingface.co/{org}/{name}/tree/main
        https://huggingface.co/datasets/{org}/{name}
    """
    m = re.search(r"huggingface\.co/(?:datasets/)?([^/]+)/([^/?#]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None


def verify_huggingface(url: str, title: str, author: str, year: str) -> dict:
    """通过 HuggingFace Hub API 验证模型/数据集页面是否存在并比对元数据。"""
    path_parts = _extract_hf_path(url)
    if not path_parts:
        return {"found": False, "reason": f"无法解析 HuggingFace URL: {url}"}

    org, repo_name = path_parts
    is_dataset = "/datasets/" in url.lower()
    repo_type = "datasets" if is_dataset else "models"
    api_url = f"https://huggingface.co/api/{repo_type}/{org}/{repo_name}"

    try:
        session = requests.Session()
        r = session.get(api_url, headers=_hf_api_headers(), timeout=20)
        if r.status_code == 404:
            return {"found": False, "reason": f"HuggingFace {repo_type[:-1]} 不存在: {org}/{repo_name}"}
        if r.status_code == 401:
            time.sleep(0.5)
            r = session.get(api_url, headers=_hf_api_headers(), timeout=20)
        if r.status_code >= 400:
            # API 不可用，回退到通用 URL 检查
            fallback = verify_general_url(url, title, author, year)
            if fallback.get("found"):
                fallback["source"] = "URL(HuggingFace/Web)"
                fallback["venue"] = "HuggingFace (page accessible)"
            return fallback
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        # 请求异常时回退到通用 URL 检查
        fallback = verify_general_url(url, title, author, year)
        if fallback.get("found"):
            fallback["source"] = "URL(HuggingFace/Web)"
            fallback["venue"] = "HuggingFace (page accessible)"
        return fallback

    if not data:
        return {"found": False, "reason": "HuggingFace API 返回空数据"}

    model_id = data.get("modelId") or data.get("id") or f"{org}/{repo_name}"
    hf_author = data.get("author") or data.get("_id", "")
    if isinstance(hf_author, dict):
        hf_author = hf_author.get("name") or hf_author.get("user") or ""
    last_modified = data.get("lastModified") or ""
    hf_year = extract_year(last_modified[:4] if last_modified else "")
    tags = data.get("tags") or []
    tag_names = [t if isinstance(t, str) else t.get("label", "") for t in tags]

    # 标题相似度：BibTeX title vs HF modelId
    sim = title_similarity(title, model_id)

    result = {
        "found": True,
        "similarity": sim,
        "matched_title": model_id,
        "author_list": _parse_author_from_org(hf_author),
        "authors": hf_author,
        "year": hf_year or data.get("lastModified", "")[:4],
        "venue": "HuggingFace",
        "type": "dataset" if is_dataset else "model",
        "doi": "",
        "url": url,
        "source": "URL(HuggingFace)",
        "tags": ", ".join(tag_names[:8]) if tag_names else "",
    }
    return result


def _extract_github_path(url: str) -> tuple[str, str] | None:
    """从 GitHub URL 中提取 (owner, repo)。

    支持:
        https://github.com/{owner}/{repo}
        https://github.com/{owner}/{repo}/tree/...
        https://github.com/{owner}/{repo}/blob/...
    """
    m = re.search(r"github\.com/([^/]+)/([^/?#]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None


def verify_github(url: str, title: str, author: str, year: str) -> dict:
    """通过 GitHub API 验证仓库是否存在并比对元数据。"""
    path_parts = _extract_github_path(url)
    if not path_parts:
        return {"found": False, "reason": f"无法解析 GitHub URL: {url}"}

    owner, repo = path_parts
    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        r = requests.get(api_url, headers={"User-Agent": "RefChecker/1.2"}, timeout=20)
        if r.status_code == 404:
            return {"found": False, "reason": f"GitHub 仓库不存在: {owner}/{repo}"}
        if r.status_code == 403 and "rate limit" in r.text.lower():
            # GitHub API 限流，回退到通用 URL 检查
            return verify_general_url(url, title, author, year)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        # API 不可用时回退到通用 URL 检查
        fallback = verify_general_url(url, title, author, year)
        if fallback.get("found"):
            fallback["source"] = "URL(GitHub/Web)"
            fallback["venue"] = "GitHub (repo page accessible)"
        return fallback

    full_name = data.get("full_name", f"{owner}/{repo}")
    gh_owner = (data.get("owner") or {}).get("login", "") if isinstance(data.get("owner"), dict) else ""
    created = data.get("created_at", "")
    gh_year = extract_year(created)
    description = data.get("description", "") or ""
    stars = data.get("stargazers_count", 0)

    # 标题相似度：BibTeX title vs GitHub full_name / description
    sim_name = title_similarity(title, full_name)
    sim_desc = title_similarity(title, description) if description else 0.0
    sim = max(sim_name, sim_desc)

    result = {
        "found": True,
        "similarity": sim,
        "matched_title": full_name,
        "author_list": _parse_author_from_org(gh_owner) if gh_owner else [],
        "authors": gh_owner,
        "year": gh_year,
        "venue": f"GitHub (stars: {stars})",
        "type": "repository",
        "doi": "",
        "url": url,
        "source": "URL(GitHub)",
    }
    return result


def verify_general_url(url: str, title: str = "", author: str = "",
                       year: str = "") -> dict:
    """通用 URL 可访问性检查（先 requests，失败时用 urllib 兜底）。"""
    headers = {"User-Agent": "RefChecker/1.2"}
    status = None

    # 先尝试 requests
    try:
        r = requests.head(url, headers=headers, timeout=15, allow_redirects=True)
        if r.status_code >= 400:
            r = requests.get(url, headers=headers, timeout=15, allow_redirects=True,
                             stream=True)
            r.close()
        status = r.status_code
    except requests.RequestException:
        status = None

    # requests 失败或返回 4xx/5xx 时用 urllib 兜底
    if status is None or status >= 400:
        try:
            import urllib.request as urllib_request
            req = urllib_request.Request(url, headers=headers)
            req.method = "HEAD"
            resp = urllib_request.urlopen(req, timeout=15)
            status = resp.status
        except Exception:
            pass

    if status is None:
        return {"found": False, "reason": "URL 不可访问"}

    if status < 200 or status >= 400:
        return {"found": False, "reason": f"URL 返回 HTTP {status}"}

    result = {
        "found": True,
        "similarity": 0.0,
        "matched_title": url,
        "author_list": [],
        "authors": "",
        "year": "",
        "venue": "Web",
        "type": "web-resource",
        "doi": "",
        "url": url,
        "source": "URL(Web)",
    }
    return result


def verify_url_resource(url: str, title: str = "", author: str = "",
                        year: str = "", email: str = "") -> dict:
    """URL 资源验证调度器：按平台分发到对应验证函数。"""
    platform = detect_url_platform(url)
    if platform == "huggingface":
        return verify_huggingface(url, title, author, year)
    elif platform == "github":
        return verify_github(url, title, author, year)
    else:
        return verify_general_url(url, title, author, year)

