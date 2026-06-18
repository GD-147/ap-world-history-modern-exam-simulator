#!/usr/bin/env python3
from pathlib import Path
import json
import re
import shutil
import sys

SRC_DIR = Path("imports/ap_world_history_modern_exams/txt")
PDF_SRC_DIR = Path("imports/ap_world_history_modern_exams/pdf")
OUT_DIR = Path("packs/ap-world-history-modern/data")
PDF_OUT_DIR = Path("packs/ap-world-history-modern/pdf")
CONFIG_PATH = Path("packs/ap-world-history-modern/config.json")

ID_RE = re.compile(r"^(APWH-(MCQ|SAQ|DBQ|LEQ)(\d+)-(\d{3}))$")
CHOICE_RE = re.compile(r"^([A-D])\)\s*(.*)$")

MCQ_KEY_RE = re.compile(
    r"^(APWH-MCQ(\d+)-\d{3})\s+[—–-]\s+Correct:\s+([A-D])\s+[—–-]\s+Correct Answer:\s+(.*?)\s+[—–-]\s+Explanation:\s+(.*)$"
)

SECTION2_RE = re.compile(
    r"\nSECTION 2\s+[—–-]\s+SERIES DO-NOT-REPEAT BANK UPDATE\s+[—–-]\s+DO NOT IMPORT",
    re.I
)

PART_B_MARKERS = [
    "PART B — ANSWER KEY + EXPLANATIONS",
    "PART B – ANSWER KEY + EXPLANATIONS",
    "PART B - ANSWER KEY + EXPLANATIONS",
]

SECTION_FILE_PREFIX = {
    "mcq": "ap_world_history_modern_mcq_exam",
    "saq": "ap_world_history_modern_saq_exam",
    "dbq": "ap_world_history_modern_dbq_exam",
    "leq": "ap_world_history_modern_leq_exam",
}

SECTION_TITLE = {
    "mcq": "AP World History: Modern MCQ Practice Exam",
    "saq": "AP World History: Modern SAQ Practice Exam",
    "dbq": "AP World History: Modern DBQ Practice Exam",
    "leq": "AP World History: Modern LEQ Practice Exam",
}

EXPECTED_COUNTS = {
    "mcq": 55,
    "saq": 3,
    "dbq": 1,
    "leq": 1,
}

EXPECTED_POINTS = {
    "saq": 3,
    "dbq": 7,
    "leq": 6,
}


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip())


def clean_multiline(s: str) -> str:
    lines = [line.rstrip() for line in str(s).strip().splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def comparable(s: str) -> str:
    return norm_space(s).lower()


def strip_do_not_import(text: str) -> str:
    m = SECTION2_RE.search(text)
    if m:
        return text[:m.start()].strip()
    return text.strip()


def split_mcq_key(text: str):
    for marker in PART_B_MARKERS:
        if marker in text:
            q_text, k_text = text.split(marker, 1)
            return q_text, k_text
    return text, ""


def parse_mcq_key(key_text: str):
    key = {}
    ignored = []
    for raw in key_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = MCQ_KEY_RE.match(line)
        if m:
            qid, exam_no, letter, correct_text, explanation = m.groups()
            key[qid] = {
                "examNo": int(exam_no),
                "correct": letter,
                "correctAnswerText": norm_space(correct_text),
                "explanation": norm_space(explanation),
            }
        elif line.startswith("APWH-MCQ"):
            ignored.append(line)
    return key, ignored


def append_field(item, field, text):
    if item.get(field):
        item[field] += "\n" + text
    else:
        item[field] = text


def parse_question_block(qid: str, kind: str, exam_no: str, block_lines):
    item = {
        "id": qid,
        "section": "",
        "type": "",
        "itemType": "",
        "unit": "",
        "period": "",
        "theme": "",
        "skill": "",
        "historicalReasoning": "",
        "sourceType": "",
        "prompt": "",
        "choices": {},
        "correct": "",
        "correctAnswerText": "",
        "explanation": "",
        "scoringGuide": "",
        "modelGuidance": "",
        "expectedPoints": "",
        "credits": 1,
    }

    current_field = None
    current_choice = None

    simple_fields = {
        "Section:": "section",
        "Type:": "type",
        "Unit:": "unit",
        "Period:": "period",
        "Theme:": "theme",
        "Skill:": "skill",
        "Historical Reasoning:": "historicalReasoning",
        "Source Type:": "sourceType",
        "Expected Points:": "expectedPoints",
    }

    multiline_fields = {
        "Prompt:": "prompt",
        "Scoring Guide:": "scoringGuide",
        "Model Guidance:": "modelGuidance",
    }

    for raw in block_lines:
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            if current_field in {"prompt", "scoringGuide", "modelGuidance"}:
                append_field(item, current_field, "")
            elif current_choice:
                item["choices"][current_choice] += "\n"
            continue

        matched = False

        for label, field in simple_fields.items():
            if stripped.startswith(label):
                item[field] = stripped.split(":", 1)[1].strip()
                current_field = None
                current_choice = None
                matched = True
                break
        if matched:
            continue

        for label, field in multiline_fields.items():
            if stripped == label:
                current_field = field
                current_choice = None
                matched = True
                break
            if stripped.startswith(label):
                item[field] = stripped.split(":", 1)[1].strip()
                current_field = field
                current_choice = None
                matched = True
                break
        if matched:
            continue

        cm = CHOICE_RE.match(stripped)
        if cm and kind == "MCQ":
            letter, value = cm.groups()
            item["choices"][letter] = value.strip()
            current_choice = letter
            current_field = None
            continue

        if current_choice and kind == "MCQ":
            item["choices"][current_choice] += "\n" + stripped
        elif current_field:
            append_field(item, current_field, stripped)

    for field in [
        "section", "type", "unit", "period", "theme", "skill",
        "historicalReasoning", "sourceType", "expectedPoints"
    ]:
        item[field] = norm_space(item.get(field, ""))

    for field in ["prompt", "scoringGuide", "modelGuidance"]:
        item[field] = clean_multiline(item.get(field, ""))

    item["choices"] = {k: norm_space(v) for k, v in item["choices"].items()}

    if kind == "MCQ":
        item["type"] = "mcq"
        item["itemType"] = "mcq"
        item["section"] = "MCQ"
        item["category"] = item["unit"]
    else:
        item["type"] = "written"
        item["itemType"] = "written"
        item["section"] = kind
        item["category"] = item["unit"]

    return item


def parse_questions(text: str):
    lines = text.splitlines()
    starts = []

    for i, line in enumerate(lines):
        s = line.strip()
        m = ID_RE.match(s)
        if m:
            qid, kind, exam_no, q_no = m.groups()
            starts.append((i, qid, kind, exam_no, q_no))

    items = []
    for idx, (start_i, qid, kind, exam_no, q_no) in enumerate(starts):
        end_i = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = lines[start_i + 1:end_i]
        items.append(parse_question_block(qid, kind, exam_no, block))

    return items


def expected_ids(kind: str, exam_no: int, count: int):
    return [f"APWH-{kind}{exam_no}-{n:03d}" for n in range(1, count + 1)]


def validate_mcq(items, mcq_key, exam_no):
    errors = []
    label = f"MCQ Exam {exam_no}"
    ids = [x["id"] for x in items]
    exp_ids = expected_ids("MCQ", exam_no, EXPECTED_COUNTS["mcq"])

    if len(items) != EXPECTED_COUNTS["mcq"]:
        errors.append(f"{label}: expected {EXPECTED_COUNTS['mcq']} questions, found {len(items)}.")

    if ids != exp_ids:
        errors.append(f"{label}: IDs must run exactly {exp_ids[0]} through {exp_ids[-1]}. Found: {ids}")

    for item in items:
        qid = item["id"]

        if item["type"] != "mcq" or item["itemType"] != "mcq":
            errors.append(f"{qid}: Type must be mcq.")

        if not item["prompt"]:
            errors.append(f"{qid}: missing Prompt.")

        if set(item["choices"].keys()) != {"A", "B", "C", "D"}:
            errors.append(f"{qid}: must have exactly choices A, B, C, D. Found {sorted(item['choices'].keys())}")

        for required in ["unit", "period", "theme", "skill"]:
            if not item.get(required):
                errors.append(f"{qid}: missing {required}.")

        if qid not in mcq_key:
            errors.append(f"{qid}: missing answer-key line.")
            continue

        k = mcq_key[qid]
        letter = k["correct"]

        if letter not in item["choices"]:
            errors.append(f"{qid}: correct letter {letter} not present in choices.")
            continue

        selected_text = item["choices"][letter]
        if comparable(selected_text) != comparable(k["correctAnswerText"]):
            errors.append(
                f"{qid}: Correct Answer text mismatch. Choice {letter} is '{selected_text}', key says '{k['correctAnswerText']}'."
            )

        item["correct"] = letter
        item["correctAnswerText"] = k["correctAnswerText"]
        item["explanation"] = k["explanation"]

    return errors


def validate_written(items, section_kind, exam_no):
    errors = []
    section_id = section_kind.lower()
    label = f"{section_kind} Exam {exam_no}"
    ids = [x["id"] for x in items]
    exp_ids = expected_ids(section_kind, exam_no, EXPECTED_COUNTS[section_id])

    if len(items) != EXPECTED_COUNTS[section_id]:
        errors.append(f"{label}: expected {EXPECTED_COUNTS[section_id]} item(s), found {len(items)}.")

    if ids != exp_ids:
        errors.append(f"{label}: IDs must run exactly {exp_ids[0]} through {exp_ids[-1]}. Found: {ids}")

    for item in items:
        qid = item["id"]

        if item["type"] != "written" or item["itemType"] != "written":
            errors.append(f"{qid}: Type must be written.")

        if item["section"] != section_kind:
            errors.append(f"{qid}: Section must be {section_kind}.")

        if not item["prompt"]:
            errors.append(f"{qid}: missing Prompt.")

        if not item["scoringGuide"]:
            errors.append(f"{qid}: missing Scoring Guide.")

        if not item["modelGuidance"]:
            errors.append(f"{qid}: missing Model Guidance.")

        for required in ["unit", "period", "theme", "historicalReasoning", "sourceType"]:
            if not item.get(required):
                errors.append(f"{qid}: missing {required}.")

        expected = EXPECTED_POINTS[section_id]
        if not item["expectedPoints"]:
            item["expectedPoints"] = expected

        try:
            pts = int(str(item["expectedPoints"]).strip())
        except ValueError:
            errors.append(f"{qid}: Expected Points must be an integer, found '{item['expectedPoints']}'.")
            continue

        if pts != expected:
            errors.append(f"{qid}: Expected Points must be {expected}, found {pts}.")

        item["expectedPoints"] = pts
        item["credits"] = pts

    return errors


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_config(section_id: str, filename: str):
    cfg = load_config()
    for section in cfg.get("sections", []):
        if section.get("id") == section_id:
            files = section.setdefault("examFiles", [])
            if filename not in files:
                files.append(filename)
            section["examFiles"] = sorted(files)
            save_config(cfg)
            return
    raise ValueError(f"Section '{section_id}' not found in config.")


def update_printables():
    cfg = load_config()
    copied = []

    if not PDF_SRC_DIR.exists():
        return copied

    PDF_OUT_DIR.mkdir(parents=True, exist_ok=True)

    for src in sorted(PDF_SRC_DIR.glob("*.pdf")):
        dst = PDF_OUT_DIR / src.name
        shutil.copy2(src, dst)
        copied.append(dst.name)

    printables = []
    for pdf in sorted(PDF_OUT_DIR.glob("*.pdf")):
        stem = pdf.stem.replace("_", " ").replace("-", " ")
        label = " ".join(word.capitalize() if word.lower() not in {"ap", "dbq", "leq", "saq", "mcq"} else word.upper() for word in stem.split())
        label = label.replace("Ap World History Modern", "AP World History: Modern")
        printables.append({"label": label, "file": pdf.name})

    cfg["printables"] = printables
    save_config(cfg)
    return copied


def write_json(section_id: str, exam_no: int, questions):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{SECTION_FILE_PREFIX[section_id]}_{exam_no:02d}.json"
    title = f"{SECTION_TITLE[section_id]} {exam_no:02d}"

    payload = {
        "title": title,
        "section": section_id,
        "questions": questions,
    }

    out_path = OUT_DIR / filename
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    update_config(section_id, filename)
    return out_path


def process_file(path: Path):
    text = strip_do_not_import(read_text(path))
    q_text, key_text = split_mcq_key(text)
    items = parse_questions(q_text)

    if not items:
        raise ValueError(f"{path.name}: no APWH question IDs found.")

    written = []

    mcq_items = [x for x in items if x["id"].startswith("APWH-MCQ")]
    if mcq_items:
        mcq_key, ignored = parse_mcq_key(key_text)
        if ignored:
            raise ValueError(f"{path.name}: malformed MCQ answer-key lines:\n" + "\n".join(ignored))

        exam_numbers = sorted({int(re.match(r"APWH-MCQ(\d+)-", x["id"]).group(1)) for x in mcq_items})
        if len(exam_numbers) != 1:
            raise ValueError(f"{path.name}: contains multiple MCQ exam numbers: {exam_numbers}")

        exam_no = exam_numbers[0]
        errors = validate_mcq(mcq_items, mcq_key, exam_no)
        if errors:
            raise ValueError(f"{path.name}: MCQ validation failed:\n- " + "\n- ".join(errors))

        written.append(write_json("mcq", exam_no, mcq_items))

    for kind in ["SAQ", "DBQ", "LEQ"]:
        section_items = [x for x in items if x["id"].startswith(f"APWH-{kind}")]
        if not section_items:
            continue

        exam_numbers = sorted({int(re.match(rf"APWH-{kind}(\d+)-", x["id"]).group(1)) for x in section_items})
        if len(exam_numbers) != 1:
            raise ValueError(f"{path.name}: contains multiple {kind} exam numbers: {exam_numbers}")

        exam_no = exam_numbers[0]
        errors = validate_written(section_items, kind, exam_no)
        if errors:
            raise ValueError(f"{path.name}: {kind} validation failed:\n- " + "\n- ".join(errors))

        written.append(write_json(kind.lower(), exam_no, section_items))

    return written


def main():
    if not SRC_DIR.exists():
        raise FileNotFoundError(f"Missing source folder: {SRC_DIR}")

    paths = sorted(SRC_DIR.glob("*.txt"))
    if not paths:
        print(f"No .txt files found in {SRC_DIR}")
    else:
        all_written = []
        for path in paths:
            print(f"Importing {path}...")
            written = process_file(path)
            all_written.extend(written)
            for out in written:
                print(f"  wrote {out}")

    copied = update_printables()
    if copied:
        print("Copied printable PDFs:")
        for name in copied:
            print(f"  {name}")

    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
