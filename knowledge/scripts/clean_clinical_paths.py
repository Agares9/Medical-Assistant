"""
清洗 2019 年版临床路径文档，只保留：
1. 诊断依据
2. 选择治疗方案的依据 / 治疗方案

输出方式：
- 按顶层科室文件夹合并为一个 txt
- 文件夹内的多个病种会拼接到同一个文件里

说明：
- .docx 使用 OpenXML 解析
- .doc 使用二进制 UTF-16 文本抽取，适合当前这批临床路径文件
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


SECTION_DIAGNOSIS = "（二）诊断依据"
SECTION_TREATMENT = "（三）选择治疗方案的依据"
SECTION_TREATMENT_ALT = "（三）治疗方案的选择"


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_docx_paragraphs(path: Path) -> List[str]:
    """从 docx 中提取段落文本。"""
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")

    paragraphs = re.findall(r"<w:p[\s\S]*?</w:p>", xml)
    lines: List[str] = []
    for para in paragraphs:
        texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", para)
        if not texts:
            continue
        line = normalize_text("".join(texts))
        if line:
            lines.append(line)
    return lines


def extract_doc_paragraphs(path: Path) -> List[str]:
    """从老 Word .doc 中抽取可读文本。

    当前 2019 临床路径 .doc 文件正文以 UTF-16LE 形式保存在二进制内容里。
    这里不做完整 Word 格式解析，只抽取正文中的章节文本。
    """
    raw_text = path.read_bytes().decode("utf-16le", errors="ignore")
    raw_text = raw_text.replace("\x00", " ")
    raw_text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", " ", raw_text)
    raw_text = re.sub(r"\s+", " ", raw_text)

    start_candidates = [
        raw_text.find("临床路径"),
        raw_text.find(SECTION_DIAGNOSIS),
        raw_text.find("一、"),
    ]
    start_candidates = [index for index in start_candidates if index >= 0]
    if start_candidates:
        raw_text = raw_text[min(start_candidates):]

    # 丢掉常见的样式/关系表残留，减少尾部乱码进入检索材料。
    for marker in ["正文文本", "HTML 预设格式", "theme/theme", "[Content_Types]", "二、"]:
        index = raw_text.find(marker)
        if index > 0:
            raw_text = raw_text[:index]

    split_text = re.sub(r"(（[一二三四五六七八九十]+）)", r"\n\1", raw_text)
    split_text = re.sub(r"(?<![A-Za-z0-9])([1-9][0-9]*[.．])", r"\n\1", split_text)
    split_text = re.sub(r"(；|。)\s*", r"\1\n", split_text)

    lines = [normalize_text(line) for line in split_text.splitlines()]
    lines = [line for line in lines if line]
    return lines


def infer_disease_name(path: Path, lines: List[str]) -> str:
    stem = path.stem
    stem = re.sub(r"（2019年版）$", "", stem)
    stem = re.sub(r"临床路径$", "", stem)
    stem = stem.strip()
    if stem:
        return stem
    return lines[0] if lines else path.stem


def find_section(lines: List[str], start_markers: Iterable[str], end_markers: Iterable[str]) -> Optional[Tuple[int, int]]:
    start = next(
        (i for i, line in enumerate(lines) if any(marker in line for marker in start_markers)),
        None,
    )
    if start is None:
        return None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if any(marker in line for marker in end_markers):
            end = i
            break
    return start, end


def extract_relevant_sections(lines: List[str]) -> List[str]:
    sections: List[str] = []

    diag = find_section(
        lines,
        [SECTION_DIAGNOSIS],
        [SECTION_TREATMENT, SECTION_TREATMENT_ALT, "（三）治疗方案", "（四）", "（五）", "（六）", "（七）"],
    )
    treat = find_section(
        lines,
        [SECTION_TREATMENT, SECTION_TREATMENT_ALT, "（三）治疗方案"],
        ["（四）", "（五）", "（六）", "（七）", "（八）"],
    )

    if diag:
        start, end = diag
        sections.append(SECTION_DIAGNOSIS)
        sections.extend(lines[start + 1:end])

    if treat:
        start, end = treat
        sections.append(SECTION_TREATMENT)
        sections.extend(lines[start + 1:end])

    return sections


def clean_one_file(source: Path) -> Optional[Tuple[str, List[str]]]:
    suffix = source.suffix.lower()
    if suffix == ".docx":
        lines = extract_docx_paragraphs(source)
    elif suffix == ".doc":
        lines = extract_doc_paragraphs(source)
    else:
        logger.warning(f"Skip unsupported file: {source.name}")
        return None

    if not lines:
        logger.warning(f"No text extracted: {source}")
        return None

    disease = infer_disease_name(source, lines)
    sections = extract_relevant_sections(lines)
    if not sections:
        logger.warning(f"No target sections found: {source.name}")
        return None

    content = [
        f"病种：{disease}",
        f"来源文件：{source.name}",
        "说明：仅保留诊断依据和治疗方案，已删除其他章节。",
        "",
    ]
    content.extend(sections)
    content.append("")
    return disease, content


def clean_one_folder(folder: Path, output_dir: Path) -> Optional[Path]:
    source_files = sorted(
        [item for item in folder.rglob("*") if item.suffix.lower() in {".docx", ".doc"}],
        key=lambda item: item.name,
    )

    if not source_files:
        logger.warning(f"No Word files in {folder.name}")
        return None

    merged: List[str] = [
        f"科室文件夹：{folder.name}",
        f"来源目录：{folder}",
        "说明：仅保留诊断依据和治疗方案，已删除其他章节。",
        "",
    ]

    written_docs = 0
    skipped_docs = 0
    for source in source_files:
        cleaned = clean_one_file(source)
        if not cleaned:
            skipped_docs += 1
            continue
        disease, content = cleaned
        merged.extend(content)
        merged.extend(["", "------", ""])
        written_docs += 1

    if written_docs == 0:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{folder.name}.txt"
    output_path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")

    if skipped_docs:
        logger.warning(f"{folder.name}: skipped {skipped_docs} files without target sections")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="清洗临床路径文档，只保留诊断依据和治疗方案")
    parser.add_argument(
        "--input",
        default=str(Path(r"D:\workfile\224个病种临床路径（2019年版）")),
        help="临床路径原始目录",
    )
    parser.add_argument(
        "--output",
        default=str(project_root / "knowledge" / "data" / "clinical_paths_cleaned_by_department"),
        help="清洗后的输出目录",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    top_level_dirs = sorted([item for item in input_dir.iterdir() if item.is_dir()])
    logger.info(f"Found {len(top_level_dirs)} top-level folders")

    written = 0
    skipped = 0
    for folder in top_level_dirs:
        out = clean_one_folder(folder, output_dir)
        if out:
            written += 1
            logger.info(f"Written: {out}")
        else:
            skipped += 1

    logger.info(f"Done. written={written}, skipped={skipped}")


if __name__ == "__main__":
    main()
