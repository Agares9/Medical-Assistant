"""
Download a focused ICD-11 common-disease subset from the WHO ICD API.

Output:
    knowledge/data/icd11_preview/18_icd11_common.txt

Environment:
    ICD_API_CLIENT_ID
    ICD_API_CLIENT_SECRET
    ICD11_RELEASE_ID       default: 2024-01
    ICD11_LANGUAGE         default: zh
    ICD11_TERMS_FILE       default: knowledge/data/icd11_terms_common.txt
    ICD11_OUTPUT_PATH      default: knowledge/data/icd11_preview/18_icd11_common.txt
"""
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from dotenv import load_dotenv
from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(project_root / ".env")

TOKEN_ENDPOINT = "https://icdaccessmanagement.who.int/connect/token"
ICD_BASE_URL = "https://id.who.int"

DEFAULT_TERMS = [
    "高血压",
    "糖尿病",
    "冠心病",
    "心力衰竭",
    "脑卒中",
    "慢性阻塞性肺疾病",
    "哮喘",
    "肺炎",
    "流行性感冒",
    "胃食管反流病",
    "胃炎",
    "消化性溃疡",
    "腹泻",
    "便秘",
    "胆石症",
    "尿路感染",
    "慢性肾脏病",
    "贫血",
    "甲状腺功能亢进症",
    "甲状腺功能减退症",
    "骨质疏松症",
    "腰痛",
    "骨关节炎",
    "类风湿关节炎",
    "偏头痛",
    "焦虑障碍",
    "抑郁障碍",
    "湿疹",
    "荨麻疹",
    "接触性皮炎",
    "痤疮",
    "过敏性鼻炎",
    "中耳炎",
    "结膜炎",
    "妊娠糖尿病",
    "痛风",
    "肥胖",
    "高脂血症",
]


def localized_text(value: Any) -> str:
    """Extract a readable label from ICD JSON-LD text fields."""
    if isinstance(value, str):
        return strip_html(value)
    if isinstance(value, dict):
        for key in ("@value", "label", "value"):
            if key in value:
                return localized_text(value[key])
    if isinstance(value, list):
        return "；".join(filter(None, (localized_text(item) for item in value)))
    return ""


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def get_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        TOKEN_ENDPOINT,
        data={"grant_type": "client_credentials", "scope": "icdapi_access"},
        auth=(client_id, client_secret),
        timeout=30,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("WHO ICD API did not return access_token")
    return token


def icd_headers(token: str, language: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": language,
        "API-Version": "v2",
    }


def normalize_api_url(url: str) -> str:
    if url.startswith("http://id.who.int"):
        return "https://id.who.int" + url[len("http://id.who.int"):]
    if url.startswith("/"):
        return ICD_BASE_URL + url
    return url


def search_icd11(term: str, token: str, release_id: str, language: str) -> List[Dict[str, Any]]:
    url = f"{ICD_BASE_URL}/icd/release/11/{release_id}/mms/search"
    response = requests.get(
        url,
        headers=icd_headers(token, language),
        params={
            "q": term,
            "flatResults": "true",
            "useFlexisearch": "true",
            "includeKeywordResult": "true",
            "medicalCodingMode": "true",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    entities = data.get("destinationEntities") or data.get("DestinationEntities") or []
    return entities[:3]


def fetch_entity(entity: Dict[str, Any], token: str, language: str) -> Dict[str, Any]:
    uri = (
        entity.get("id")
        or entity.get("@id")
        or entity.get("linearizationUri")
        or entity.get("linearizationURI")
    )
    if not uri:
        return entity
    response = requests.get(
        normalize_api_url(uri),
        headers=icd_headers(token, language),
        timeout=30,
    )
    response.raise_for_status()
    detail = response.json()
    return {**entity, **detail}


def entity_to_record(term: str, entity: Dict[str, Any]) -> Dict[str, str]:
    code = (
        entity.get("theCode")
        or entity.get("code")
        or entity.get("stemId")
        or ""
    )
    title = (
        localized_text(entity.get("title"))
        or localized_text(entity.get("label"))
        or localized_text(entity.get("matchingTitle"))
        or localized_text(entity.get("stemTitle"))
    )
    definition = localized_text(entity.get("definition"))
    synonyms = localized_text(entity.get("synonym") or entity.get("indexTerm"))
    uri = entity.get("@id") or entity.get("id") or entity.get("linearizationUri") or ""

    return {
        "query": term,
        "code": code,
        "title": title,
        "definition": definition,
        "synonyms": synonyms,
        "uri": uri,
    }


def load_terms(path: Optional[Path]) -> List[str]:
    if not path:
        return DEFAULT_TERMS
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


def format_records(records: Iterable[Dict[str, str]], release_id: str, language: str) -> str:
    lines = [
        "ICD-11 常见病种编码和分类描述",
        "",
        f"来源：WHO ICD-11 MMS API",
        f"版本：{release_id}",
        f"语言：{language}",
        "说明：本文件用于疾病分类和标准编码辅助，不作为诊断或治疗依据。",
        "",
    ]

    for record in records:
        lines.extend([
            f"疾病查询词：{record['query']}",
            f"ICD-11编码：{record['code'] or '未返回'}",
            f"标准名称：{record['title'] or '未返回'}",
            f"定义描述：{record['definition'] or '暂无'}",
            f"同义词/索引词：{record['synonyms'] or '暂无'}",
            f"URI：{record['uri'] or '暂无'}",
            "",
        ])

    return "\n".join(lines).strip() + "\n"


def main():
    client_id = os.getenv("ICD_API_CLIENT_ID", "").strip()
    client_secret = os.getenv("ICD_API_CLIENT_SECRET", "").strip()
    release_id = os.getenv("ICD11_RELEASE_ID", "2024-01").strip()
    language = os.getenv("ICD11_LANGUAGE", "zh").strip()
    terms_file = os.getenv(
        "ICD11_TERMS_FILE",
        str(project_root / "knowledge" / "data" / "icd11_terms_common.txt"),
    ).strip()
    output_path = Path(os.getenv(
        "ICD11_OUTPUT_PATH",
        project_root / "knowledge" / "data" / "icd11_preview" / "18_icd11_common.txt",
    ))

    if not client_id or not client_secret:
        raise SystemExit("请在 .env 中设置 ICD_API_CLIENT_ID 和 ICD_API_CLIENT_SECRET")

    terms_path = Path(terms_file) if terms_file else None
    terms = load_terms(terms_path if terms_path and terms_path.exists() else None)
    if terms_path and not terms_path.exists():
        logger.warning(f"ICD11_TERMS_FILE does not exist, using built-in defaults: {terms_path}")
    logger.info(f"Preparing to download ICD-11 subset: terms={len(terms)}, release={release_id}, lang={language}")

    token = get_token(client_id, client_secret)
    records = []

    for term in terms:
        try:
            logger.info(f"Searching ICD-11: {term}")
            candidates = search_icd11(term, token, release_id, language)
            if not candidates:
                logger.warning(f"No ICD-11 result for: {term}")
                records.append({
                    "query": term,
                    "code": "",
                    "title": "",
                    "definition": "",
                    "synonyms": "",
                    "uri": "",
                })
                continue
            detail = fetch_entity(candidates[0], token, language)
            records.append(entity_to_record(term, detail))
        except Exception as e:
            logger.error(f"Failed to download term '{term}': {e}")
            records.append({
                "query": term,
                "code": "",
                "title": "",
                "definition": f"下载失败：{e}",
                "synonyms": "",
                "uri": "",
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_records(records, release_id, language), encoding="utf-8")
    logger.info(f"Saved ICD-11 common subset: {output_path}")
    logger.info("下一步运行：python knowledge/scripts/import_hardcoded_data.py")


if __name__ == "__main__":
    main()
