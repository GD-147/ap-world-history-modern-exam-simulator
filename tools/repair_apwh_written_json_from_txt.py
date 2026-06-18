from pathlib import Path
import json
import re

TXT_DIR = Path("imports/ap_world_history_modern_exams/txt")
DATA_DIR = Path("packs/ap-world-history-modern/data")

FIELD_MAP = {
    "Unit": "unit",
    "Period": "period",
    "Theme": "theme",
    "Historical Reasoning": "historicalReasoning",
    "Source Type": "sourceType",
}

def clean(s):
    return "\n".join(line.rstrip() for line in s.strip().splitlines()).strip()

def section_from_id(qid):
    m = re.match(r"APWH-(SAQ|DBQ|LEQ)(\d+)-\d{3}$", qid)
    if not m:
        raise ValueError(f"Invalid written ID: {qid}")
    return m.group(1).lower(), int(m.group(2))

def extract_between(block, start_label, end_label):
    pat = rf"(?ms)^{re.escape(start_label)}:\s*\n(.*?)(?=^{re.escape(end_label)}:\s*$)"
    m = re.search(pat, block)
    if not m:
        raise ValueError(f"Could not extract {start_label} before {end_label}")
    return clean(m.group(1))

def extract_last(block, start_label):
    pat = rf"(?ms)^{re.escape(start_label)}:\s*\n(.*)$"
    m = re.search(pat, block)
    if not m:
        raise ValueError(f"Could not extract {start_label}")
    return clean(m.group(1))

def parse_meta(pre_prompt):
    meta = {}
    for line in pre_prompt.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k in FIELD_MAP and k not in meta:
            meta[FIELD_MAP[k]] = v
    return meta

updated = 0
json_cache = {}

for txt_path in sorted(TXT_DIR.glob("*frq*_exam_*.txt")) + sorted(TXT_DIR.glob("*free_response*_exam_*.txt")):
    text = txt_path.read_text(encoding="utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    matches = list(re.finditer(r"(?m)^(APWH-(?:SAQ|DBQ|LEQ)\d+-\d{3})\s*$", text))
    if not matches:
        print(f"No written IDs found in {txt_path.name}")
        continue

    for i, m in enumerate(matches):
        qid = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        prompt_marker = re.search(r"(?m)^Prompt:\s*$", block)
        if not prompt_marker:
            raise ValueError(f"{qid}: missing Prompt:")

        pre_prompt = block[:prompt_marker.start()]
        meta = parse_meta(pre_prompt)

        prompt = extract_between(block, "Prompt", "Scoring Guide")
        scoring = extract_between(block, "Scoring Guide", "Model Guidance")
        model = extract_between(block, "Model Guidance", "Expected Points")
        expected_raw = extract_last(block, "Expected Points")
        expected_match = re.search(r"\d+", expected_raw)
        expected_points = int(expected_match.group(0)) if expected_match else None

        section, exam_num = section_from_id(qid)
        json_path = DATA_DIR / f"ap_world_history_modern_{section}_exam_{exam_num:02d}.json"

        if json_path not in json_cache:
            json_cache[json_path] = json.loads(json_path.read_text(encoding="utf-8"))

        data = json_cache[json_path]
        found = False
        for q in data.get("questions", []):
            if q.get("id") == qid:
                q.update(meta)
                q["prompt"] = prompt
                q["scoringGuide"] = scoring
                q["modelGuidance"] = model
                q["expectedPoints"] = expected_points
                found = True
                updated += 1
                break

        if not found:
            raise ValueError(f"{qid}: not found in {json_path}")

for json_path, data in json_cache.items():
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Repaired {json_path}")

print(f"Updated written questions: {updated}")
