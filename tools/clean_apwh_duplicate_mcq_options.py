from pathlib import Path
import re
import shutil

TXT_DIR = Path("imports/ap_world_history_modern_exams/txt")

targets = sorted(TXT_DIR.glob("*mcq*exam_02.txt")) + sorted(TXT_DIR.glob("*mcq*exam_03.txt"))

if not targets:
    print("No MCQ Exam 2/3 files found. Check filenames.")
    raise SystemExit(0)

def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

def split_answer_key(text: str):
    m = re.search(r"(?im)^PART\s+B\s*[—–-]\s*ANSWER\s+KEY.*$", text)
    if not m:
        return text, ""
    return text[:m.start()], text[m.start():]

def option_signature(block: str):
    opts = []
    for letter in "ABCD":
        m = re.search(rf"(?ms)^{letter}[\).]\s*(.*?)(?=^[A-D][\).]\s*|\Z)", block)
        if not m:
            return None
        val = " ".join(m.group(1).split()).strip()
        opts.append(val)
    return tuple(opts)

def remove_duplicate_option_groups(question_block: str):
    # Finds repeated A-D option groups inside one question block.
    # Keeps the first complete A-D set and removes later identical complete A-D sets.
    starts = list(re.finditer(r"(?m)^A[\).]\s*", question_block))
    if len(starts) < 2:
        return question_block, 0

    removed = 0
    out = question_block

    while True:
        starts = list(re.finditer(r"(?m)^A[\).]\s*", out))
        if len(starts) < 2:
            break

        changed = False
        first_start = starts[0].start()

        # End of first A-D group = before next A) or end of question.
        first_end = starts[1].start()
        first_group = out[first_start:first_end]
        first_sig = option_signature(first_group)

        if not first_sig:
            break

        for s in starts[1:]:
            second_start = s.start()
            next_a = None
            for later in starts:
                if later.start() > second_start:
                    next_a = later.start()
                    break
            second_end = next_a if next_a is not None else len(out)
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

def clean_questions_section(text: str):
    body, answer_key = split_answer_key(text)

    # Split on APWH-MCQ IDs when present. If not present, still attempt whole-body cleanup.
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

for path in targets:
    original = path.read_text(encoding="utf-8-sig")
    normalized = normalize_newlines(original)

    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)

    cleaned, removed = clean_questions_section(normalized)
    path.write_text(cleaned, encoding="utf-8")

    print(f"{path.name}: removed duplicate A-D groups = {removed}; backup = {backup.name}")
