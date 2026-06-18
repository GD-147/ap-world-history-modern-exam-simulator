// app/runner.js

function decodeHtmlEntitiesDeep(text = "") {
  let s = String(text);

  for (let i = 0; i < 3; i++) {
    const ta = document.createElement("textarea");
    ta.innerHTML = s;
    const decoded = ta.value;
    if (decoded === s) break;
    s = decoded;
  }

  return s;
}

function renderInlineMarkup(text = "") {
  let s = decodeHtmlEntitiesDeep(text);

  // lascia passare solo tag semplici e sicuri
  s = s.replace(/<(?!\/?(u|i|br)\b)[^>]*>/gi, "");

  return s;
}

function normalizeQuestion(q) {
  const choices = {};
  for (const [k, v] of Object.entries(q.choices || {})) {
    choices[String(k)] = decodeHtmlEntitiesDeep(v);
  }

  const rawType = String(q.itemType || q.type || "").trim().toLowerCase();
  const itemType =
    rawType === "constructed" || rawType === "constructed_response"
      ? "constructed_response"
      : "mcq_single";

  return {
    ...q,
    itemType,
    part: String(q.part || "").trim(),
    credits: Number(q.credits || 0),
    prompt: decodeHtmlEntitiesDeep(q.prompt || ""),
    instruction: decodeHtmlEntitiesDeep(q.instruction || ""),
    explanation: decodeHtmlEntitiesDeep(q.explanation || ""),
    modelAnswer: decodeHtmlEntitiesDeep(q.modelAnswer || ""),
    scoringGuidance: decodeHtmlEntitiesDeep(q.scoringGuidance || ""),
    rubric: decodeHtmlEntitiesDeep(q.rubric || ""),
    choices
  };
}
function getPartLabel(q) {
  const part = String(q.part || "").trim();
  const credits = Number(q.credits || 0);
  const creditText = credits ? `${credits} credit${credits === 1 ? "" : "s"}` : "";
  return [part ? `Part ${part}` : "", creditText].filter(Boolean).join(" — ");
}

function getDefaultInstruction(q) {
  if (q.itemType === "constructed_response") {
    return "Show your work. Use the response box to write your reasoning and final answer.";
  }

  return "Select one answer choice.";
}

function answerDraftKey(examId, sectionId, qid) {
  return `constructedDraft_${examId}_${sectionId}_${qid}`;
}
async function loadQuestionsForSection(examId, section) {
  const files = (section.examFiles && section.examFiles.length)
    ? section.examFiles
    : [];

  const all = [];
  if (!files.length) return all;

  for (const f of files) {
    const path = `../packs/${examId}/data/${f}`;
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) throw new Error(`Missing question file: ${path}`);

    const raw = await res.json();
    const rawQuestions = Array.isArray(raw)
      ? raw
      : (Array.isArray(raw.questions) ? raw.questions : []);
    const arr = rawQuestions.map(normalizeQuestion);

    all.push({ file: f, questions: arr });
  }
  return all; // [{file, questions}, ...]
}

function fmtTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
function decodeHtmlEntitiesDeep(text = "") {
  let s = String(text);

  for (let i = 0; i < 3; i++) {
    const ta = document.createElement("textarea");
    ta.innerHTML = s;
    const decoded = ta.value;

    if (decoded === s) break;
    s = decoded;
  }

  return s;
}

function renderInlineMarkup(text = "") {
  let s = decodeHtmlEntitiesDeep(text);

  // lascia passare solo tag semplici e sicuri
  s = s.replace(/<(?!\/?(u|i|br)\b)[^>]*>/gi, "");

  return s;
}
function practiceCursorKey(examId, sectionId) {
  return `practiceCursor_${examId}_${sectionId}`;
}

function getPracticeSlice(allQs, chunkSize, examId, sectionId) {
  const key = practiceCursorKey(examId, sectionId);
  let cursor = parseInt(localStorage.getItem(key) || "0", 10);

  if (cursor >= allQs.length) cursor = 0;

  const start = cursor;
  const end = Math.min(cursor + chunkSize, allQs.length);

  const slice = allQs.slice(start, end);

  cursor = end;
  if (cursor >= allQs.length) cursor = 0;
  localStorage.setItem(key, String(cursor));

  return { slice, start, end, total: allQs.length };
}



function qs(id) { return document.getElementById(id); }

(async function () {
  const examId = getExamFromUrl();
  if (!isAccessGranted(examId)) { goToWelcome(examId); return; }

  const cfg = await loadConfig(examId);
  applyTheme(cfg.theme || "dark");
  qs("brand").textContent = cfg.brandName;
  qs("logo").src = cfg.logoPath;

  const params = new URLSearchParams(window.location.search);
  const sectionId = params.get("section");
  const mode = params.get("mode"); // "exam" | "practice"

  const section = cfg.sections.find(s => s.id === sectionId);
  if (!section) {
    qs("title").textContent = "Error";
    qs("desc").textContent = "Unknown section.";
    return;
  }

  // ===== WRITTEN RESPONSE MODE =====
  if (section.type === "frq" || section.type === "written") {
    const examSets = await loadQuestionsForSection(examId, section);
    const setsWithQs = examSets.filter(s => Array.isArray(s.questions) && s.questions.length);

    if (!setsWithQs.length) {
      qs("title").textContent = "No written-response section available";
      qs("desc").textContent = "No written-response questions were found for this section. Check the imported JSON file and config.json.";
      return;
    }

    function getField(obj, ...names) {
      for (const name of names) {
        if (obj && obj[name] !== undefined && obj[name] !== null && String(obj[name]).trim() !== "") {
          return obj[name];
        }
      }
      return "";
    }

    function countWords(text) {
      return text && text.trim() ? text.trim().split(/\s+/).length : 0;
    }

    let frqQs = [];
    let metaText = "";

    if (mode === "practice") {
      const pooledPrompts = setsWithQs.flatMap(s => s.questions || []);
      const key = `writtenCursor_${examId}_${sectionId}`;
      let cur = parseInt(localStorage.getItem(key) || "0", 10);
      if (!Number.isFinite(cur) || cur < 0 || cur >= pooledPrompts.length) cur = 0;
      frqQs = [pooledPrompts[cur]];
      localStorage.setItem(key, String((cur + 1) % pooledPrompts.length));
      metaText = `Practice prompt: ${frqQs[0].id || "Written item"}`;
    } else {
      const rotKey = `writtenRotation_${examId}_${sectionId}`;
      let rot = parseInt(localStorage.getItem(rotKey) || "0", 10);
      if (!Number.isFinite(rot) || rot < 0 || rot >= setsWithQs.length) rot = 0;
      const chosen = setsWithQs[rot];
      localStorage.setItem(rotKey, String((rot + 1) % setsWithQs.length));
      frqQs = (chosen.questions || []).slice(0, section.examQuestions || 6);
      metaText = chosen.title || "AP World History: Modern Written-Response Section";
    }

    if (!frqQs.length || !frqQs[0].prompt) {
      qs("title").textContent = "Written prompt error";
      qs("desc").textContent = "The written-response file loaded, but the prompt field is missing.";
      return;
    }

    qs("runnerPanel").classList.add("hidden");
    qs("resultsPanel").classList.add("hidden");
    qs("essayPanel").classList.remove("hidden");
    qs("essayResultsPanel").classList.add("hidden");

    qs("essayTitle").textContent = `${section.label} — ${mode === "practice" ? "Practice Mode" : "Exam Mode"}`;
    qs("essayDesc").textContent = mode === "practice"
      ? "Untimed written-response practice. Use this to rehearse AP World History: Modern source analysis, historical reasoning, and written explanations."
      : `Timed written-response section: ${section.timeMin} minutes.`;

    let timerInterval = null;
    let remaining = section.timeMin * 60;
    const startTime = Date.now();

    const timerEl = qs("timer");
    if (mode !== "practice") {
      if (timerEl) timerEl.classList.remove("hidden");
      if (timerEl) timerEl.textContent = fmtTime(remaining);
      timerInterval = setInterval(() => {
        remaining--;
        if (timerEl) timerEl.textContent = fmtTime(Math.max(0, remaining));
        if (remaining <= 0) finishFrq();
      }, 1000);
    } else if (timerEl) {
      timerEl.classList.add("hidden");
    }

    let current = 0;
    const box = qs("essayText");

    function draftKey(q) {
      return `draft_${examId}_${sectionId}_${q.id || current}`;
    }

    const responses = frqQs.map(q => localStorage.getItem(draftKey(q)) || "");

    function saveCurrent() {
      responses[current] = box.value;
      localStorage.setItem(draftKey(frqQs[current]), box.value);
    }

    function updateWordCount() {
      qs("wordCount").textContent = String(countWords(box.value));
    }

    function renderFrq() {
      const q = frqQs[current];
      const qId = q.id || `Written item ${current + 1}`;
      const frqType = getField(q, "sourceType", "historicalReasoning", "frqType", "typeLabel", "frq_type");
      const expectedPoints = getField(q, "expectedPoints", "expected_points", "points");
      const primaryUnit = getField(q, "primaryUnit", "unit", "category");
      const metaBits = [
        metaText,
        `Question ${current + 1} of ${frqQs.length}`,
        qId,
        frqType,
        primaryUnit,
        expectedPoints ? `${expectedPoints} points` : ""
      ].filter(Boolean);

      qs("essayMeta").textContent = metaBits.join(" • ");
      qs("essayPrompt").innerHTML = renderInlineMarkup(q.prompt || "");
      box.value = responses[current] || "";
      updateWordCount();

      const prevBtn = document.getElementById("frqPrevBtn");
      const nextBtn = document.getElementById("frqNextBtn");
      if (prevBtn) prevBtn.disabled = current === 0;
      if (nextBtn) nextBtn.disabled = current === frqQs.length - 1;
    }

    box.addEventListener("input", () => {
      updateWordCount();
      responses[current] = box.value;
      localStorage.setItem(draftKey(frqQs[current]), box.value);
    });

    const saveBtn = qs("essaySaveBtn");
    if (saveBtn) {
      saveBtn.addEventListener("click", () => {
        saveCurrent();
        saveBtn.textContent = "Saved";
        setTimeout(() => { saveBtn.textContent = "Save"; }, 900);
      });
    }

    const prevBtn = document.getElementById("frqPrevBtn");
    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        saveCurrent();
        if (current > 0) current--;
        renderFrq();
      });
    }

    const nextBtn = document.getElementById("frqNextBtn");
    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        saveCurrent();
        if (current < frqQs.length - 1) current++;
        renderFrq();
      });
    }

    function finishFrq() {
      saveCurrent();
      if (timerInterval) clearInterval(timerInterval);

      const elapsedSec = Math.floor((Date.now() - startTime) / 1000);
      const completed = responses.filter(r => r && r.trim()).length;
      const blank = frqQs.length - completed;
      const totalWords = responses.reduce((sum, r) => sum + countWords(r), 0);

      qs("essayPanel").classList.add("hidden");
      qs("essayResultsPanel").classList.remove("hidden");

      qs("essayTimeLine").textContent = `Time used: ${fmtTime(elapsedSec)}`;
      qs("essayWordLine").textContent = `Completed responses: ${completed}/${frqQs.length} • Blank: ${blank} • Total word count: ${totalWords}`;

      const modelGuidanceEl = qs("essayModelGuidance");
      if (modelGuidanceEl) {
        modelGuidanceEl.innerHTML = `<strong>Self-review message:</strong><br>Free-response answers are not auto-scored. Compare your work with the scoring guide below.`;
      }

      const rubricEl = qs("essayRubric");
      if (rubricEl) {
        rubricEl.innerHTML = frqQs.map((q, idx) => {
          const qId = q.id || `Written item ${idx + 1}`;
          const scoring = getField(q, "scoringGuide", "rubric", "scoring_guide") || "No scoring guide provided.";
          const guidance = getField(q, "modelGuidance", "modelAnswer", "model_guidance") || "Review whether your response answers the prompt, uses accurate historical evidence, and supports claims with clear historical reasoning.";
          const points = getField(q, "expectedPoints", "expected_points", "points");
          return `
            <div class="reviewCard" style="margin-top:14px;">
              <h3 style="margin:0 0 8px;">${qId}${points ? ` — ${points} points` : ""}</h3>
              <div><strong>Scoring Guide:</strong><br>${renderInlineMarkup(String(scoring))}</div>
              <div style="margin-top:10px;"><strong>Model Guidance:</strong><br>${renderInlineMarkup(String(guidance))}</div>
            </div>
          `;
        }).join("");
      }

      qs("essayHomeBtn").onclick = () => {
        window.location.href = `app.html?exam=${encodeURIComponent(examId)}`;
      };
    }

    qs("essayFinishBtn").addEventListener("click", finishFrq);

    qs("backLink").addEventListener("click", (e) => {
      e.preventDefault();
      saveCurrent();
      window.location.href = `app.html?exam=${encodeURIComponent(examId)}`;
    });

    renderFrq();
    return;
  }

  // Carica domande MCQ (supporta più examFiles)
  const examSets = await loadQuestionsForSection(examId, section);

  // Pool globale per Practice Mode (tutte le domande di tutti gli exam)
  const pooledQs = examSets.flatMap(s => s.questions);

  if (!pooledQs.length) {
    qs("title").textContent = "No practice files available yet";
    qs("desc").textContent = "No imported practice file is currently available for this section. Import a valid .txt source file first, then reload the simulator.";
    const metaEl = qs("metaLine");
    if (metaEl) metaEl.textContent = "";
    return;
  }

  // Scegli set domande per la sessione
let sessionQs;
let metaText = "";

if (mode === "practice") {
  const info = getPracticeSlice(pooledQs, cfg.practiceChunkSize || 10, examId, sectionId);
  sessionQs = info.slice;
  metaText = `Practice block: ${info.start + 1}–${info.end} of ${info.total}`;
} else {
  const rotKey = `examRotation_${examId}_${sectionId}`;
  let rot = parseInt(localStorage.getItem(rotKey) || "0", 10);
  if (rot >= examSets.length) rot = 0;

  const chosen = examSets[rot];
  localStorage.setItem(rotKey, String((rot + 1) % examSets.length));

  const n = Math.min(section.examQuestions, chosen.questions.length);
  sessionQs = chosen.questions.slice(0, n);

  metaText = `Loaded set: ${chosen.file}`;
}

// stampa subito la riga meta
const metaEl = qs("metaLine");
if (metaEl) metaEl.textContent = metaText;


  // UI state
  let idx = 0;
  const answers = {}; // q.id -> "A"/"B"/"C"/"D"
  const startTime = Date.now();

  // Timer (solo Exam Mode)
  let timerInterval = null;
  let remaining = section.timeMin * 60;

  function render() {
    const q = sessionQs[idx];
    qs("title").textContent = `${section.label} — ${mode === "practice" ? "Practice Mode" : "Exam Mode"}`;
    qs("desc").textContent = mode === "practice"
      ? `10-question set (progress cycles automatically).`
      : `Timed full section: ${sessionQs.length} questions in ${section.timeMin} minutes.`;

      qs("metaLine").textContent = metaText;

    qs("progress").textContent = `Question ${idx + 1} of ${sessionQs.length}`;

    const partEl = qs("itemPart");
    if (partEl) partEl.textContent = getPartLabel(q);

    const instructionEl = qs("itemInstruction");
    if (instructionEl) instructionEl.textContent = q.instruction || getDefaultInstruction(q);

    qs("prompt").innerHTML = renderInlineMarkup(q.prompt);

    const box = qs("choices");
    box.innerHTML = "";

    if (q.itemType === "constructed_response") {
      const wrap = document.createElement("div");
      wrap.className = "constructedWrap";

      const label = document.createElement("label");
      label.className = "label";
      label.textContent = "Your Response";

      const textarea = document.createElement("textarea");
      textarea.className = "essayBox";
      textarea.placeholder = "Write your work, reasoning, and final answer here.";

      const draftKey = answerDraftKey(examId, sectionId, q.id);
      const saved = answers[q.id] ?? localStorage.getItem(draftKey) ?? "";
      textarea.value = saved;
      answers[q.id] = saved;

      textarea.addEventListener("input", () => {
        answers[q.id] = textarea.value;
        localStorage.setItem(draftKey, textarea.value);
      });

      const helper = document.createElement("p");
      helper.className = "helper";
      helper.textContent = "Your response is saved automatically in this browser.";

      wrap.appendChild(label);
      wrap.appendChild(textarea);
      wrap.appendChild(helper);
      box.appendChild(wrap);
    } else {
      ["A","B","C","D"].forEach(letter => {
        if (!q.choices || q.choices[letter] == null) return;

        const row = document.createElement("label");
        row.className = "choice";

        const input = document.createElement("input");
        input.type = "radio";
        input.name = `choice_${q.id}`;
        input.value = letter;
        input.checked = answers[q.id] === letter;

        input.addEventListener("change", () => {
          answers[q.id] = letter;
        });

        const span = document.createElement("span");
        span.className = "choiceText";
        span.innerHTML = `${letter}. ${renderInlineMarkup(q.choices[letter])}`;

        row.appendChild(input);
        row.appendChild(span);
        box.appendChild(row);
      });
    }

    qs("prevBtn").disabled = idx === 0;
    qs("nextBtn").disabled = idx === sessionQs.length - 1;
  }

  function finish() {
    if (timerInterval) clearInterval(timerInterval);

    const elapsedSec = Math.floor((Date.now() - startTime) / 1000);

    const mcqQs = sessionQs.filter(q => q.itemType !== "constructed_response");
    const constructedQs = sessionQs.filter(q => q.itemType === "constructed_response");

    let correct = 0;
    let earnedAutoCredits = 0;
    let possibleAutoCredits = 0;
    let possibleConstructedCredits = 0;

    mcqQs.forEach(q => {
      const credits = Number(q.credits || 0);
      possibleAutoCredits += credits;
      if ((answers[q.id] || "") === q.correct) {
        correct++;
        earnedAutoCredits += credits;
      }
    });

    constructedQs.forEach(q => {
      possibleConstructedCredits += Number(q.credits || 0);
    });

    const pct = mcqQs.length ? Math.round((correct / mcqQs.length) * 100) : 0;

    qs("runnerPanel").classList.add("hidden");
    qs("resultsPanel").classList.remove("hidden");

    qs("scoreLine").textContent =
      `Auto-scored MCQ: ${pct}% (${correct}/${mcqQs.length} correct, ${earnedAutoCredits}/${possibleAutoCredits} credits). ` +
      `Constructed responses: ${constructedQs.length} question${constructedQs.length === 1 ? "" : "s"} for self-review` +
      `${possibleConstructedCredits ? ` (${possibleConstructedCredits} possible credits).` : "."}`;

    qs("timeLine").textContent = `Time used: ${fmtTime(elapsedSec)}`;

    const review = qs("review");
    review.innerHTML = "";

    sessionQs.forEach((q, i) => {
      const isConstructed = q.itemType === "constructed_response";
      const user = answers[q.id] || "(no answer)";
      const ok = !isConstructed && user === q.correct;

      const block = document.createElement("div");
      block.className = "reviewBlock";

      const num = document.createElement("div");
      num.className = isConstructed ? "qnum" : (ok ? "qnum qnum-ok" : "qnum qnum-bad");
      num.textContent = `Q${i + 1}`;

      const text = document.createElement("div");
      text.className = "reviewText";

      const part = document.createElement("div");
      part.className = "reviewAns";
      part.textContent = getPartLabel(q);

      const p = document.createElement("div");
      p.className = "reviewPrompt";
      p.innerHTML = renderInlineMarkup(q.prompt);

      text.appendChild(part);
      text.appendChild(p);

      if (isConstructed) {
        const a = document.createElement("div");
        a.className = "reviewAns";
        a.textContent = `Your response: ${user}`;

        const model = document.createElement("div");
        model.className = "reviewExp";
        model.innerHTML = q.modelAnswer
          ? `<strong>Model answer:</strong><br>${renderInlineMarkup(q.modelAnswer)}`
          : "<strong>Model answer:</strong><br>Review the scoring guidance for this response.";

        const guidance = document.createElement("div");
        guidance.className = "reviewExp";
        guidance.innerHTML = q.scoringGuidance || q.rubric
          ? `<strong>Scoring guidance:</strong><br>${renderInlineMarkup(q.scoringGuidance || q.rubric)}`
          : "<strong>Scoring guidance:</strong><br>No rubric provided for this item.";

        text.appendChild(a);
        text.appendChild(model);
        text.appendChild(guidance);
      } else {
        const a = document.createElement("div");
        a.className = "reviewAns";
        a.textContent = `Your answer: ${user}    |    Correct: ${q.correct}`;

        const ex = document.createElement("div");
        ex.className = "reviewExp";
        ex.textContent = q.explanation;

        text.appendChild(a);
        text.appendChild(ex);
      }

      block.appendChild(num);
      block.appendChild(text);
      review.appendChild(block);
    });
  }

  if (mode !== "practice") {
    const timerEl = qs("timer");
    if (timerEl) timerEl.classList.remove("hidden");
    if (timerEl) timerEl.textContent = fmtTime(remaining);

    timerInterval = setInterval(() => {
      remaining--;
      if (timerEl) timerEl.textContent = fmtTime(Math.max(0, remaining));
      if (remaining <= 0) finish();
    }, 1000);
  }

  qs("prevBtn").addEventListener("click", () => { if (idx > 0) { idx--; render(); } });
  qs("nextBtn").addEventListener("click", () => { if (idx < sessionQs.length - 1) { idx++; render(); } });
  qs("finishBtn").addEventListener("click", finish);

  qs("backLink").addEventListener("click", (e) => {
    e.preventDefault();
    window.location.href = `app.html?exam=${encodeURIComponent(examId)}`;
  });

  qs("homeBtn").addEventListener("click", () => {
    window.location.href = `app.html?exam=${encodeURIComponent(examId)}`;
  });

  render();
})();
