/* 과목선택 내비게이터 — 프론트엔드 (vanilla JS SPA, 빌드 스텝 없음)
 * 서버 저장 없음: 상태는 localStorage + 공유 링크(URL 직렬화)에만 존재.
 * 화면 코드는 MAPS_자체서비스_화면설계_v1.md(v1.1) 기준: S0→S1→S2→S3→S3.5→S4→S5→S6→S7
 */
(() => {
  "use strict";
  const $app = document.getElementById("app");
  const API = "/api";

  // ── 관심 칩 (수기 큐레이션, 최소셋) ──
  const CHIPS = [
    { emoji: "🐾", label: "동물" }, { emoji: "🧪", label: "실험" },
    { emoji: "🎨", label: "그림" }, { emoji: "💻", label: "코딩" },
    { emoji: "🏥", label: "돌봄" }, { emoji: "⚖️", label: "정의" },
    { emoji: "🎤", label: "무대" }, { emoji: "✈️", label: "여행" },
    { emoji: "🔬", label: "탐구" }, { emoji: "🏗️", label: "건축" },
    { emoji: "📈", label: "경영" }, { emoji: "🍳", label: "요리" },
    { emoji: "⚽", label: "운동" }, { emoji: "🎬", label: "영상" },
    { emoji: "🌱", label: "환경" }, { emoji: "🧮", label: "수리" },
    { emoji: "📖", label: "글쓰기" }, { emoji: "🤖", label: "로봇" },
    { emoji: "🎼", label: "음악" }, { emoji: "🗣️", label: "설득" },
    { emoji: "🧑‍🏫", label: "가르침" }, { emoji: "🌏", label: "세계" },
    { emoji: "🧵", label: "손재주" }, { emoji: "🛰️", label: "우주" },
  ];

  // ── 상태 ──
  const STORE_KEY = "maps_state_v1";
  function defaultState() {
    return {
      profile: { sido: "", gugun: "", school_id: "", school_name: "", grade: "고1", semester: 1 },
      taken: [],       // [{subject, status: "이수함"|"신청함"}]
      interests: { utterance: "", chips: [] },
      candidates: null, // /api/recommend 응답
      currentMajor: null,
      plan: [],         // [{subject, from_major}]
      seenSheetFor: [],  // S3.5를 이미 본 학과 이름들
    };
  }
  let S = loadState();
  function loadState() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) return Object.assign(defaultState(), JSON.parse(raw));
    } catch (e) {}
    return defaultState();
  }
  function saveState() {
    localStorage.setItem(STORE_KEY, JSON.stringify(S));
  }
  function resetState() {
    S = defaultState();
    saveState();
  }

  // ── 공유 링크 (URL 직렬화, 서버 저장 없음) ──
  function b64encode(obj) {
    return btoa(unescape(encodeURIComponent(JSON.stringify(obj))))
      .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function b64decode(str) {
    str = str.replace(/-/g, "+").replace(/_/g, "/");
    while (str.length % 4) str += "=";
    return JSON.parse(decodeURIComponent(escape(atob(str))));
  }
  function buildShareUrl() {
    const payload = {
      profile: S.profile, taken: S.taken, plan: S.plan, interests: S.interests,
    };
    const url = new URL(location.href);
    url.search = "";
    url.searchParams.set("share", b64encode(payload));
    return url.toString();
  }

  // ── API 헬퍼 ──
  async function api(path, opts) {
    const res = await fetch(API + path, opts);
    if (!res.ok) {
      let msg = "요청 중 문제가 생겼어";
      try { msg = (await res.json()).detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    return res.json();
  }
  async function apiGet(path) { return api(path); }
  async function apiPost(path, body) {
    return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  }

  // ── 라우팅 ──
  let screen = "s0";
  function go(next) { screen = next; render(); window.scrollTo(0, 0); }

  function planBadge() {
    if (screen === "s7read") return "";
    const n = S.plan.length;
    return `<span class="plan-badge" onclick="window.__go('s5')">${n}</span>`;
  }
  function topbar(title, backTo) {
    return `<div class="topbar">
      ${backTo ? `<button class="back" onclick="window.__go('${backTo}')">←</button>` : ""}
      <div class="title">${title}</div>
      ${planBadge()}
    </div>`;
  }

  // ══════════════════════════════════════════════════════════════
  // S0 — 학교·학년
  // ══════════════════════════════════════════════════════════════
  async function renderS0() {
    const sidos = (await apiGet("/sidos")).sidos;
    const p = S.profile;
    $app.innerHTML = `
      <div class="screen">
        <h1>과목선택 내비게이터</h1>
        <p class="sub">네 학교에서 실제로 신청할 수 있는 과목으로 알려줄게</p>

        <div class="field-label">학교 찾기</div>
        <select id="f-sido"><option value="">시도 선택</option>
          ${sidos.map(s => `<option ${p.sido===s?"selected":""}>${s}</option>`).join("")}
        </select>
        <select id="f-gugun" style="margin-top:8px" ${p.sido?"":"disabled"}>
          <option value="">시군구 선택</option>
        </select>
        <input id="f-school-q" type="text" placeholder="학교 이름 검색" style="margin-top:8px" ${p.gugun?"":"disabled"}>
        <div id="f-school-list" style="margin-top:8px"></div>
        <div id="f-school-picked" style="margin-top:8px;font-size:14px;color:var(--accent-2)">
          ${p.school_name ? `✓ ${p.school_name} 선택됨` : ""}
        </div>

        <div class="field-label">학년</div>
        <div class="seg" id="f-grade">
          <button data-v="고1" class="${p.grade==="고1"?"active":""}">고1</button>
          <button data-v="고2" class="${p.grade==="고2"?"active":""}">고2</button>
        </div>
        <div id="f-sem-wrap" class="seg" style="${p.grade==="고1"?"":"display:none"}">
          <button data-v="1" class="${p.semester===1?"active":""}">1학기</button>
          <button data-v="2" class="${p.semester===2?"active":""}">2학기</button>
        </div>
        <div class="banner" style="margin-top:16px">
          지금은 2025년 이후 입학생(2022 개정 교육과정, 고1·고2)만 도와줄 수 있어요.
        </div>

        <button class="btn-primary" id="btn-start" ${p.school_id?"":"disabled"}>시작하기 →</button>
        <p class="footer-note">학교 과목 정보: 학교알리미 2025·2026 공시 기준</p>
      </div>`;

    const $sido = document.getElementById("f-sido");
    const $gugun = document.getElementById("f-gugun");
    const $q = document.getElementById("f-school-q");
    const $list = document.getElementById("f-school-list");

    async function refreshGuguns() {
      if (!$sido.value) { $gugun.innerHTML = `<option value="">시군구 선택</option>`; $gugun.disabled = true; return; }
      const { guguns } = await apiGet("/guguns?sido=" + encodeURIComponent($sido.value));
      $gugun.innerHTML = `<option value="">시군구 선택</option>` + guguns.map(g => `<option ${p.gugun===g?"selected":""}>${g}</option>`).join("");
      $gugun.disabled = false;
    }
    async function refreshSchools() {
      $list.innerHTML = "";
      if (!$gugun.value) { $q.disabled = true; return; }
      $q.disabled = false;
      const { schools } = await apiGet(`/schools?sido=${encodeURIComponent($sido.value)}&gugun=${encodeURIComponent($gugun.value)}&q=${encodeURIComponent($q.value)}`);
      $list.innerHTML = schools.slice(0, 12).map(s =>
        `<div class="btn-small" style="display:block;margin-bottom:6px;text-align:left" data-id="${s.shl_idf_cd}" data-name="${s.school}">${s.school}</div>`
      ).join("") || `<div class="banner">이 지역 학교를 찾지 못했어. 이름을 다시 검색해봐.</div>`;
      $list.querySelectorAll("[data-id]").forEach(el => {
        el.onclick = () => {
          S.profile.school_id = el.dataset.id;
          S.profile.school_name = el.dataset.name;
          saveState();
          document.getElementById("f-school-picked").innerHTML = `✓ ${el.dataset.name} 선택됨`;
          document.getElementById("btn-start").disabled = false;
        };
      });
    }
    $sido.onchange = () => { S.profile.sido = $sido.value; S.profile.gugun = ""; S.profile.school_id = ""; S.profile.school_name = ""; saveState(); refreshGuguns(); $list.innerHTML=""; };
    $gugun.onchange = () => { S.profile.gugun = $gugun.value; S.profile.school_id = ""; S.profile.school_name = ""; saveState(); refreshSchools(); };
    $q.oninput = debounce(refreshSchools, 250);
    document.getElementById("f-grade").querySelectorAll("button").forEach(b => {
      b.onclick = () => {
        S.profile.grade = b.dataset.v; saveState();
        document.getElementById("f-sem-wrap").style.display = b.dataset.v === "고1" ? "flex" : "none";
        renderS0();
      };
    });
    const $sem = document.getElementById("f-sem-wrap");
    if ($sem) $sem.querySelectorAll("button").forEach(b => {
      b.onclick = () => { S.profile.semester = Number(b.dataset.v); saveState(); renderS0(); };
    });
    document.getElementById("btn-start").onclick = () => go("s1");

    if (p.sido) await refreshGuguns();
    if (p.gugun) await refreshSchools();
  }

  function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

  // ══════════════════════════════════════════════════════════════
  // S1 — 관심 입력
  // ══════════════════════════════════════════════════════════════
  function renderS1() {
    $app.innerHTML = `
      ${topbar(S.profile.school_name + " · " + S.profile.grade, "s0")}
      <div class="screen">
        <h2>요즘 뭐가 제일 끌려?</h2>
        <p class="sub">한 마디면 충분해</p>
        <input id="f-speech" type="text" placeholder="예: 동물 돌보는 일이 좋아요" value="${escapeHtml(S.interests.utterance)}">

        <div class="divider-label">아니면 골라봐 (2~3개)</div>
        <div class="chip-grid" id="chip-grid">
          ${CHIPS.map(c => `<div class="chip ${S.interests.chips.includes(c.label)?"sel":""}" data-l="${c.label}">
            <div class="emoji">${c.emoji}</div><div>${c.label}</div></div>`).join("")}
        </div>

        <button class="btn-primary" id="btn-go">말한 걸로 찾기</button>
        <div id="err" class="banner warn" style="display:none;margin-top:12px"></div>
      </div>`;

    document.getElementById("chip-grid").querySelectorAll(".chip").forEach(el => {
      el.onclick = () => {
        const l = el.dataset.l;
        const i = S.interests.chips.indexOf(l);
        if (i >= 0) S.interests.chips.splice(i, 1);
        else if (S.interests.chips.length < 3) S.interests.chips.push(l);
        el.classList.toggle("sel");
        saveState();
      };
    });
    document.getElementById("f-speech").oninput = (e) => { S.interests.utterance = e.target.value; saveState(); };
    document.getElementById("btn-go").onclick = async () => {
      const $err = document.getElementById("err");
      $err.style.display = "none";
      if (!S.interests.utterance.trim() && S.interests.chips.length === 0) {
        $err.textContent = "한 마디만 말해주거나 칩을 하나 골라줘.";
        $err.style.display = "block";
        return;
      }
      try {
        const res = await apiPost("/recommend", { speech: S.interests.utterance, chips: S.interests.chips });
        S.candidates = res;
        saveState();
        go("s2");
      } catch (e) {
        $err.textContent = "잠깐 문제가 생겼어. 다시 시도해줄래?";
        $err.style.display = "block";
      }
    };
  }

  // ══════════════════════════════════════════════════════════════
  // S2 — 갈래 → 후보 카드
  // ══════════════════════════════════════════════════════════════
  function renderS2() {
    const c = S.candidates;
    if (!c) return go("s1");
    $app.innerHTML = `
      ${topbar("이런 갈래로 이어져", "s1")}
      <div class="screen">
        ${c.empty ? `
          <div class="empty-state">
            <div class="emoji">🤔</div>
            <p>맞는 걸 못 찾았어. 이렇게 말해볼래?</p>
            <p class="sub">"동물 돌보는 일" · "그림 그리는 거" · "사람들 앞에서 말하는 거"</p>
            <button class="btn-ghost" onclick="window.__go('s1')">다시 입력하기</button>
          </div>` : `
          <p class="sub">점수·순위는 없어. 근거만 보여줄게</p>
          ${c.categories.map(cat => `
            <div class="card">
              <div class="cat-head">${cat.emoji} ${cat.dae}</div>
              ${cat.majors.map(m => `
                <div class="card-major" data-major="${escapeHtml(m.name)}">
                  <div class="name">${m.name}</div>
                  ${m.summary ? `<div class="summary">${m.summary}</div>` : ""}
                  <div class="reason">근거: ${m.reason}</div>
                </div>
              `).join("")}
            </div>
          `).join("")}
          <button class="btn-ghost" onclick="window.__go('s1')">다른 갈래 볼래</button>
        `}
      </div>`;
    $app.querySelectorAll(".card-major").forEach(el => {
      el.onclick = () => { S.currentMajor = el.dataset.major; saveState(); go("s3"); };
    });
  }

  // ══════════════════════════════════════════════════════════════
  // S3 — 학과 상세: 권장과목 · 성취기준 · 설치대학
  // ══════════════════════════════════════════════════════════════
  let s3detailCache = {};
  async function renderS3() {
    const name = S.currentMajor;
    if (!name) return go("s2");
    if (!s3detailCache[name]) s3detailCache[name] = await apiGet("/major/" + encodeURIComponent(name));
    const d = s3detailCache[name];
    const takenSet = new Map(S.taken.map(t => [t.subject, t.status]));

    function subjectRow(typ, s) {
      const st = takenSet.get(s);
      const badge = st === "이수함" ? `<span class="badge done">✓ 하는 중</span>`
                  : st === "신청함" ? `<span class="badge applied">📝 신청함</span>` : "";
      return `<div class="subject-row" data-ach="${escapeHtml(s)}">
        <span class="sname">${s}</span>${badge}
      </div><div class="ach-box" id="ach-${cssId(s)}"></div>`;
    }

    const univ = d.universities || {};
    const regions = univ.by_region || {};
    const univHtml = Object.keys(regions).length ? Object.entries(regions).map(([region, list]) => `
      <div style="margin-bottom:10px"><b>${region}</b>
      ${list.map(u => `<div style="font-size:13px;color:var(--text-dim);margin:4px 0">
        ${u.대학명} · ${(u.전형||[]).join(", ")} · 규모 ${sizeLabel(u.인원)}</div>`).join("")}
      </div>`).join("") : `<div class="banner">설치대학 정보가 아직 없어.</div>`;

    $app.innerHTML = `
      ${topbar(name, "s2")}
      <div class="screen">
        <h2>2·3학년 때 이런 과목이 도움 돼</h2>
        <p class="sub" style="margin-bottom:8px">커리어넷 학과정보 기준</p>
        ${["일반","진로","융합"].map(typ => (d.subjects[typ]||[]).length ? `
          <div class="subject-group">
            <h3>${typ}선택</h3>
            ${d.subjects[typ].map(s => subjectRow(typ, s)).join("")}
          </div>` : "").join("")}

        <details class="collapsible">
          <summary>설치대학 더 보기</summary>
          <div style="margin-top:8px">${univHtml}</div>
        </details>
        ${d.related_jobs && d.related_jobs.length ? `
        <details class="collapsible">
          <summary>연계 직업 더 보기</summary>
          <div style="margin-top:8px;font-size:14px">${d.related_jobs.join(" · ")}</div>
        </details>` : ""}

        <button class="btn-primary" id="btn-avail">우리 학교에 있는지 확인 →</button>
      </div>`;

    $app.querySelectorAll(".subject-row").forEach(el => {
      el.onclick = async () => {
        const subj = el.dataset.ach;
        const box = document.getElementById("ach-" + cssId(subj));
        if (box.classList.contains("open")) { box.classList.remove("open"); return; }
        if (!box.dataset.loaded) {
          const a = await apiGet(`/major/${encodeURIComponent(name)}/achievement?subject=${encodeURIComponent(subj)}`);
          box.innerHTML = a.items.length
            ? a.items.map(it => `<div style="margin-bottom:6px">"${it.text}"</div>`).join("")
            : `<div>성취기준 정보가 아직 없어.</div>`;
          box.dataset.loaded = "1";
        }
        box.classList.add("open");
      };
    });

    document.getElementById("btn-avail").onclick = () => {
      const allSubs = ["일반","진로","융합"].flatMap(t => d.subjects[t] || []);
      if (S.seenSheetFor.includes(name)) return go("s4");
      openTakenSheet(allSubs, () => { S.seenSheetFor.push(name); saveState(); go("s4"); });
    };
  }
  function sizeLabel(n) {
    n = Number(n) || 0;
    if (n <= 5) return "소규모"; if (n <= 15) return "중간규모"; return "대규모";
  }
  function cssId(s) { return s.replace(/[^a-zA-Z0-9가-힣]/g, ""); }

  // ══════════════════════════════════════════════════════════════
  // S3.5 — 이수체크 시트 (just-in-time bottom sheet)
  // ══════════════════════════════════════════════════════════════
  function openTakenSheet(subjects, onDone) {
    const overlay = document.createElement("div");
    overlay.className = "sheet-overlay";
    overlay.innerHTML = `
      <div class="sheet">
        <h2>확인 전에 하나만!</h2>
        <p class="sub" style="margin-bottom:10px">이 중에 벌써 듣고 있는 게 있어? (없으면 건너뛰어도 돼)</p>
        <div id="sheet-rows">
          ${subjects.map(s => sheetRow(s)).join("")}
        </div>
        <div style="font-size:13px;color:var(--text-dim);margin:8px 0">ⓘ 1학년 공통과목(국어·수학·통합과학 등)은 체크 안 해도 돼</div>
        <input id="sheet-search" type="text" placeholder="+ 다른 과목도 들었어 (검색)">
        <div id="sheet-search-results" style="margin-top:6px"></div>
        <div class="sheet-footer">
          <div class="count" id="sheet-count">0개 체크됨</div>
          <button class="action-btn ghost" id="sheet-skip">건너뛰기</button>
          <button class="action-btn" id="sheet-done">확인하러 가기</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    function sheetRow(s) {
      const st = statusOf(s);
      return `<div class="sheet-row" data-s="${escapeHtml(s)}">
        <span class="sname">${s}</span>
        <div class="btns">
          <button class="btn-small ${st==="이수함"?"on":""}" data-set="이수함">들었어</button>
          <button class="btn-small ${st==="신청함"?"on":""}" data-set="신청함">신청해뒀어</button>
        </div>
      </div>`;
    }
    function statusOf(s) { const t = S.taken.find(x => x.subject === s); return t ? t.status : null; }
    function setStatus(s, status) {
      const idx = S.taken.findIndex(x => x.subject === s);
      const cur = idx >= 0 ? S.taken[idx].status : null;
      if (cur === status) { if (idx >= 0) S.taken.splice(idx, 1); }
      else if (idx >= 0) S.taken[idx].status = status;
      else S.taken.push({ subject: s, status });
      saveState();
    }
    function refreshCount() {
      overlay.querySelector("#sheet-count").textContent = `${S.taken.length}개 체크됨`;
    }
    function bindRows(root) {
      root.querySelectorAll(".sheet-row").forEach(row => {
        row.querySelectorAll("button[data-set]").forEach(btn => {
          btn.onclick = () => {
            setStatus(row.dataset.s, btn.dataset.set);
            row.querySelectorAll("button").forEach(b => b.classList.remove("on"));
            if (statusOf(row.dataset.s) === btn.dataset.set) btn.classList.add("on");
            refreshCount();
          };
        });
      });
    }
    bindRows(overlay);
    refreshCount();

    const $search = overlay.querySelector("#sheet-search");
    $search.oninput = debounce(async () => {
      const q = $search.value.trim();
      const box = overlay.querySelector("#sheet-search-results");
      if (!q) { box.innerHTML = ""; return; }
      const { subjects: found } = await apiGet("/subjects/search?q=" + encodeURIComponent(q));
      box.innerHTML = found.slice(0, 8).map(s => sheetRow(s.name)).join("");
      bindRows(box);
    }, 250);

    overlay.querySelector("#sheet-skip").onclick = () => { overlay.remove(); onDone(); };
    overlay.querySelector("#sheet-done").onclick = () => { overlay.remove(); onDone(); };
  }

  // ══════════════════════════════════════════════════════════════
  // S4 — 우리 학교 개설여부 × 내 이수 현황
  // ══════════════════════════════════════════════════════════════
  let firstVisitModalShown = false;
  async function renderS4() {
    const name = S.currentMajor;
    const avail = await apiGet(`/availability?major=${encodeURIComponent(name)}&school=${encodeURIComponent(S.profile.school_id)}`);
    const takenMap = new Map(S.taken.map(t => [t.subject, t.status]));
    const planSet = new Set(S.plan.map(p => p.subject));

    let cHave=0, cCan=0, cNo=0, cQ=0;
    const rows = [];
    ["일반","진로","융합"].forEach(typ => {
      (avail.by_type[typ] || []).forEach(item => {
        const st = takenMap.get(item.subject);
        let kind;
        if (!avail.have_school) { kind = "q"; cQ++; }
        else if (st === "이수함") { kind = "done"; cHave++; }
        else if (st === "신청함") { kind = "applied"; cHave++; }
        else if (item.offered) { kind = "ok"; cCan++; }
        else { kind = "no"; cNo++; }
        rows.push({ typ, subject: item.subject, kind, status: st });
      });
    });

    $app.innerHTML = `
      ${topbar(S.profile.school_name + " 개설 현황", "s3")}
      <div class="screen">
        <p class="sub" style="margin-bottom:4px">2025·2026 공시 기준</p>
        <div class="summary-line">
          <b>${name}</b> 권장 ${rows.length}과목 중<br>
          이미 하는 중 <b>${cHave}</b> · 담을 수 있어 <b>${cCan}</b> ·
          우리 학교엔 없어 <b>${cNo}</b> · 확인 필요 <b>${cQ}</b>
        </div>
        ${!avail.have_school ? `<div class="banner warn">이 학교 과목 정보가 아직 없어 — 담임선생님께 확인해줘.</div>` : ""}

        ${rows.map(r => rowHtml(r)).join("")}

        <div class="banner" style="margin-top:16px">ⓘ 신청 전 담임선생님과 꼭 확인해줘</div>
      </div>`;

    function rowHtml(r) {
      const icon = r.kind === "no" ? "⬜" : r.kind === "q" ? "❓" : "✅";
      let right;
      if (r.kind === "done") right = `<span class="badge done">✓ 하는 중 (고치기)</span>`;
      else if (r.kind === "applied") right = `<span class="badge applied">📝 신청해뒀네 →</span>`;
      else if (r.kind === "ok") right = planSet.has(r.subject)
        ? `<span class="badge done">담음</span>`
        : `<button class="action-btn sm" data-add="${escapeHtml(r.subject)}">목록에 담기</button>`;
      else if (r.kind === "no") right = `<button class="action-btn ghost sm" data-alt="${escapeHtml(r.subject)}">대안 보기 →</button>`;
      else right = `<span class="badge q">담임 확인</span>`;
      return `<div class="subject-row">
        <span class="sname">${icon} ${r.subject}</span>${right}
      </div>`;
    }

    $app.querySelectorAll("[data-add]").forEach(el => {
      el.onclick = () => {
        S.plan.push({ subject: el.dataset.add, from_major: name });
        saveState(); renderS4();
      };
    });
    $app.querySelectorAll("[data-alt]").forEach(el => {
      el.onclick = () => { S.altSubject = el.dataset.alt; go("s6"); };
    });
    $app.querySelectorAll(".badge.applied").forEach(el => {
      el.onclick = () => {
        const subj = el.closest(".subject-row").querySelector(".sname").textContent.replace(/^\S+\s/, "");
        if (!S.plan.some(p => p.subject === subj)) S.plan.push({ subject: subj, from_major: name });
        saveState();
        alert("좋아, 그대로 목록에 담아둘게. 마음이 바뀌면 목록에서 언제든 뺄 수 있어.");
        renderS4();
      };
    });

    if (!firstVisitModalShown) {
      firstVisitModalShown = true;
      const m = document.createElement("div");
      m.className = "modal";
      m.innerHTML = `<div class="modal-box">
        <p><b>과목 선택이 합불을 정하지 않아요.</b><br>어떤 과목을 골랐는지가 대학 합격을 결정하지 않아. 참고만 하고, 진짜 결정은 담임선생님과 함께해줘.</p>
        <button class="btn-primary" id="m-ok">알겠어</button>
      </div>`;
      document.body.appendChild(m);
      m.querySelector("#m-ok").onclick = () => m.remove();
    }
  }

  // ══════════════════════════════════════════════════════════════
  // S5 — 담임쌤과 상의할 목록 (결승선)
  // ══════════════════════════════════════════════════════════════
  function renderS5() {
    const doneTaken = S.taken.filter(t => t.status === "이수함");
    $app.innerHTML = `
      ${topbar("내 목록 · " + S.profile.school_name, "s4")}
      <div class="screen">
        <h2>담임쌤과 상의할 목록</h2>
        <div class="banner">실제 개설 학년·학기와 신청 가능 개수는 학교 편제표에 따라 달라 — 그래서 담임쌤과 상의가 필요해</div>

        ${S.plan.length === 0 ? `
          <div class="empty-state">
            <div class="emoji">📭</div><p>아직 담은 게 없어.</p>
            <button class="btn-ghost" onclick="window.__go('s2')">추천으로 돌아갈래?</button>
          </div>` : `
          <div class="plan-block">
            <h3>상의할 과목</h3>
            ${S.plan.map((p,i) => `<div class="plan-item">
              <span class="sname">${p.subject} ${p.status==="신청함"?"📝":""}</span>
              <button class="remove-btn" data-i="${i}">빼기</button>
            </div>`).join("")}
          </div>`}

        ${doneTaken.length ? `
          <div class="plan-block">
            <h3>이미 하고 있는 과목</h3>
            ${doneTaken.map(t => `<div class="plan-item done"><span class="sname">✓ ${t.subject}</span></div>`).join("")}
          </div>` : ""}

        ${S.plan.length ? `<div style="font-size:13px;color:var(--text-dim);margin:8px 0 20px">
          이 목록이 이어주는 진로: <b>${[...new Set(S.plan.map(p=>p.from_major))].join(" · ")}</b>
        </div>` : ""}

        <button class="btn-primary" id="btn-share">공유 링크 만들기</button>
        <button class="btn-ghost" id="btn-print">이미지로 저장(인쇄)</button>
        <div id="share-out" style="margin-top:12px"></div>
      </div>`;

    $app.querySelectorAll("[data-i]").forEach(el => {
      el.onclick = () => { S.plan.splice(Number(el.dataset.i), 1); saveState(); renderS5(); };
    });
    document.getElementById("btn-print").onclick = () => window.print();
    document.getElementById("btn-share").onclick = () => {
      const url = buildShareUrl();
      document.getElementById("share-out").innerHTML =
        `<div class="banner">이 링크를 담임선생님께 보여드려:<br><a class="link" href="${url}">${url}</a></div>`;
      if (navigator.clipboard) navigator.clipboard.writeText(url).catch(() => {});
    };
  }

  // ══════════════════════════════════════════════════════════════
  // S6 — 미개설 대안
  // ══════════════════════════════════════════════════════════════
  function renderS6() {
    const subj = S.altSubject || "";
    $app.innerHTML = `
      ${topbar("'" + subj + "'이 우리 학교에 없을 때", "s4")}
      <div class="screen">
        <p class="sub">안 열렸다고 길이 닫힌 건 아니야</p>

        <div class="card">
          <div class="cat-head">① 학교 밖에서 듣는 길</div>
          <div style="font-size:14px;color:var(--text-dim);line-height:1.8">
            · 학교 간 공동교육과정<br>
            · 시도 온라인학교 / 교실온닷<br>
            (담임선생님·교육과정부장님께 문의해줘)
          </div>
        </div>

        <div class="banner">ⓘ 개설 신청이 많으면 학교가 열기도 해 — 수요조사에 꼭 적어봐</div>
        <button class="btn-ghost" onclick="window.__go('s4')">← 돌아가기</button>
      </div>`;
  }

  // ══════════════════════════════════════════════════════════════
  // S7 (읽기전용) — 공유 링크로 들어온 경우
  // ══════════════════════════════════════════════════════════════
  function renderS7Read(data) {
    const taken = data.taken || [];
    const plan = data.plan || [];
    $app.innerHTML = `
      <div class="topbar"><div class="title">학생 플랜 요약</div></div>
      <div class="screen">
        <h2>${data.profile.school_name || ""} · ${data.profile.grade || ""}</h2>
        <p class="sub">관심: ${escapeHtml(data.interests?.utterance || (data.interests?.chips||[]).join(", ") || "-")}</p>

        <div class="plan-block">
          <h3>상의할 과목</h3>
          ${plan.length ? plan.map(p => `<div class="plan-item"><span class="sname">${p.subject}</span></div>`).join("")
            : `<p class="sub">아직 없음</p>`}
        </div>
        <div class="plan-block">
          <h3>이수 체크</h3>
          ${taken.length ? taken.map(t => `<div class="plan-item done"><span class="sname">${t.status==="이수함"?"✓":"📝"} ${t.subject}</span></div>`).join("")
            : `<p class="sub">아직 없음</p>`}
        </div>

        <p class="footer-note">데이터: 학교알리미 2025·2026 공시 기준 · 학생 셀프체크 기반(참고용)</p>
        <button class="btn-primary" id="btn-try">나도 해보기</button>
      </div>`;
    document.getElementById("btn-try").onclick = () => {
      const url = new URL(location.href); url.search = ""; location.href = url.toString();
    };
  }

  // ── 유틸 ──
  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
  }

  // ── 렌더 디스패치 ──
  function render() {
    if (screen === "s0") return renderS0();
    if (screen === "s1") return renderS1();
    if (screen === "s2") return renderS2();
    if (screen === "s3") return renderS3();
    if (screen === "s4") return renderS4();
    if (screen === "s5") return renderS5();
    if (screen === "s6") return renderS6();
  }
  window.__go = go;

  // ── 부트스트랩 ──
  const params = new URLSearchParams(location.search);
  if (params.get("share")) {
    try {
      const data = b64decode(params.get("share"));
      renderS7Read(data);
    } catch (e) {
      $app.innerHTML = `<div class="screen"><p>공유 링크를 읽을 수 없어.</p></div>`;
    }
  } else {
    render();
  }
})();
