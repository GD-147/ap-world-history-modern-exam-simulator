from pathlib import Path
import re
import shutil

TXT_DIR = Path("imports/ap_world_history_modern_exams/txt")

target_re = re.compile(r".*mcq.*exam_(0[6-9]|1[0-2])\.txt$", re.I)
targets = sorted(
    p for p in TXT_DIR.glob("*.txt")
    if target_re.match(p.name) and ".bak" not in p.name
)

if not targets:
    print("No MCQ Exam 6-12 files found.")
    raise SystemExit(0)

def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")

def split_answer_key(text):
    m = re.search(r"(?im)^PART\s+B\s*[—–-]\s*ANSWER\s+KEY.*$", text)
    if not m:
        return text, ""
    return text[:m.start()], text[m.start():]

def option_signature(block):
    opts = []
    for letter in "ABCD":
        m = re.search(rf"(?ms)^{letter}[\).]\s*(.*?)(?=^[A-D][\).]\s*|\Z)", block)
        if not m:
            return None
        opts.append(" ".join(m.group(1).split()).strip())
    return tuple(opts)

def remove_duplicate_option_groups(question_block):
    starts = list(re.finditer(r"(?m)^A[\).]\s*", question_block))
    if len(starts) < 2:
        return question_block, 0

    removed = 0
    out = question_block

    while True:
        starts = list(re.finditer(r"(?m)^A[\).]\s*", out))
        if len(starts) < 2:
            break

        first_start = starts[0].start()
        first_end = starts[1].start()
        first_group = out[first_start:first_end]
        first_sig = option_signature(first_group)

        if not first_sig:
            break

        changed = False

        for index, s in enumerate(starts[1:], start=1):
            second_start = s.start()
            second_end = starts[index + 1].start() if index + 1 < len(starts) else len(out)
            second_group = out[second_start:second_end]
            second_sig = option_signature(second_group)

            if second_sig == first_sig:
                out = out[:second_start].rstrip() + "\n" + out[second_end:].lstrip()
                removed += 1
                changed = True
                break

        if not changed:
            break

    return out, removed

def clean_questions_section(text):
    body, answer_key = split_answer_key(text)
    parts = re.split(r"(?m)^(APWH-MCQ\d+-\d{3})\s*$", body)
    total_removed = 0

    if len(parts) >= 3:
        rebuilt = [parts[0]]
        for i in range(1, len(parts), 2):
            qid = parts[i]
            qblock = parts[i + 1] if i + 1 < len(parts) else ""
            cleaned, removed = remove_duplicate_option_groups(qblock)
            total_removed += removed
            rebuilt.append(qid + "\n")
            rebuilt.append(cleaned)
        body = "".join(rebuilt)
    else:
        body, total_removed = remove_duplicate_option_groups(body)

    return body.rstrip() + "\n\n" + answer_key.lstrip(), total_removed

def count_question_options(text):
    body, _ = split_answer_key(text)
    return {
        "question_ids": len(re.findall(r"(?m)^APWH-MCQ\d+-\d{3}\s*$", body)),
        "A": len(re.findall(r"(?m)^A[\).]\s+", body)),
        "B": len(re.findall(r"(?m)^B[\).]\s+", body)),
        "C": len(re.findall(r"(?m)^C[\).]\s+", body)),
        "D": len(re.findall(r"(?m)^D[\).]\s+", body)),
    }

for path in targets:
    original = path.read_text(encoding="utf-8-sig")
    normalized = normalize_newlines(original)

    before = count_question_options(normalized)

    backup = path.with_suffix(path.suffix + ".dedupe.bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    cleaned, removed = clean_questions_section(normalized)
    path.write_text(cleaned, encoding="utf-8")

    after = count_question_options(cleaned)

    print("")
    print(path.name)
    print("  duplicate A-D groups removed:", removed)
    print("  before:", before)
    print("  after: ", after)
