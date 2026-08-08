"""
统一构建本地医学知识库。

支持数据源：
- knowledge/data/documents/*.txt
- knowledge/data/clinical_paths_cleaned_by_department/*.txt
- knowledge/data/icd11_preview/*.txt

用法：
    python knowledge/scripts/build_knowledge_base.py --preview
    python knowledge/scripts/build_knowledge_base.py --rebuild
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def read_text_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(folder.glob("*.txt"))


def make_document(doc_id: str, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": doc_id, "content": content, "metadata": metadata}


def load_documents() -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []

    source_specs = [
        (
            "knowledge/data/documents",
            "core",
            lambda path: "ICD-11" if "icd11" in path.name.lower() else "core",
            lambda path: "原始知识文档",
        ),
        (
            "knowledge/data/icd11_preview",
            "disease_classification",
            lambda path: "WHO ICD-11 MMS API",
            lambda path: "ICD-11 常见病种子集",
        ),
        (
            "knowledge/data/clinical_paths_cleaned_by_department",
            "clinical_path",
            lambda path: path.stem,
            lambda path: "2019年版临床路径（按科室清洗）",
        ),
    ]

    for rel_dir, default_type, source_fn, source_label_fn in source_specs:
        folder = project_root / rel_dir
        files = read_text_files(folder)
        logger.info(f"Scanning {folder}: {len(files)} txt files")

        for txt_file in files:
            content = txt_file.read_text(encoding="utf-8").strip()
            if not content:
                continue

            filename = txt_file.stem
            doc_type = default_type
            source = source_fn(txt_file)

            if rel_dir == "knowledge/data/documents":
                parts = filename.split("_", 2)
                if len(parts) >= 2:
                    file_num = parts[0]
                    try:
                        num = int(file_num)
                        if 0 <= num < 10:
                            doc_type = "lifestyle"
                            source = "生活方式建议数据库"
                        elif 10 <= num < 20:
                            doc_type = "disease_classification"
                            source = "WHO ICD-11 MMS API" if "icd11" in filename.lower() or "ICD-11" in content else "ICD-10疾病编码数据库"
                        elif 20 <= num < 30:
                            doc_type = "clinical_guideline"
                            source = "临床指南数据库"
                    except ValueError:
                        doc_type = "general"
                disease_name = parts[2] if len(parts) > 2 else filename
            elif rel_dir == "knowledge/data/clinical_paths_cleaned_by_department":
                doc_type = "clinical_path"
                disease_name = filename
            else:
                disease_name = filename

            docs.append(make_document(
                doc_id=f"{doc_type}_{filename}",
                content=content,
                metadata={
                    "type": doc_type,
                    "disease": disease_name,
                    "source": source_label_fn(txt_file) if rel_dir != "knowledge/data/documents" else source,
                    "filename": txt_file.name,
                    "folder": txt_file.parent.name,
                    "source_dir": rel_dir,
                },
            ))

    return docs


def group_summary(documents: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for doc in documents:
        counts[doc["metadata"].get("type", "unknown")] = counts.get(doc["metadata"].get("type", "unknown"), 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="统一构建本地医学知识库")
    parser.add_argument("--preview", action="store_true", help="只打印统计，不导入")
    parser.add_argument("--rebuild", action="store_true", help="删除现有 collection 后重建")
    args = parser.parse_args()

    documents = load_documents()
    if not documents:
        logger.error("No documents loaded from knowledge/data")
        return

    counts = group_summary(documents)
    logger.info(f"Loaded {len(documents)} documents")
    for key, value in sorted(counts.items()):
        logger.info(f"  - {key}: {value}")

    if args.preview:
        logger.info("Preview mode, skip import")
        return

    from knowledge.milvus_kb import MedicalKnowledgeBase

    kb = MedicalKnowledgeBase()
    if args.rebuild:
        logger.warning("Dropping existing knowledge collection before rebuild")
        kb.delete_collection()
        MedicalKnowledgeBase._instance = None
        kb = MedicalKnowledgeBase()

    added = kb.add_documents(documents)
    logger.info(f"Imported {added} chunks into Milvus")


if __name__ == "__main__":
    main()
