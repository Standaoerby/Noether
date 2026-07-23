// check_front_contract.mjs — E2 Ф1: the reads the slice front actually performs, executed
// against the REAL package, in JS, outside a browser.
//
// The canvas cannot be gated headlessly, so this does not pretend to. What it DOES gate is the
// part that breaks silently: the data contract. For a sample of ticks it reproduces, verbatim,
// what `updateFocus()` and the estate-outline loop read out of the package —
//   owned cells := B.owners filtered by FOCUS      (the dashed outline)
//   position    := B.pawns.find(p => p[0]===FOCUS) (the gold ring)
//   card        := cards.json entries[FOCUS]       (arc + evidence + narrative)
// — and asserts they resolve at EVERY tick, i.e. that map, card and caption can be read at one
// and the same T. Python's run_slice_gates proves the same thing from the other side; this
// proves the JS side is looking at fields that exist.
//
// Run:  node viz/slice/check_front_contract.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = join(HERE, "data");
const jsonl = (f) => readFileSync(join(DATA, f), "utf8").split("\n")
  .filter((l) => l.trim()).map((l) => JSON.parse(l));

const meta = JSON.parse(readFileSync(join(DATA, "meta.json"), "utf8"));
const cards = JSON.parse(readFileSync(join(DATA, "cards.json"), "utf8"));
const snaps = jsonl("snapshots.jsonl");
const events = jsonl("events.jsonl");

let bad = 0;
const fail = (m) => { console.log("  ✗ " + m); bad++; };

console.log("=".repeat(78));
console.log("E2 Ф1 — контракт фронта (node, реальный пакет viz/slice/data)");
console.log("=".repeat(78));
console.log(`пакет: ${snaps.length} снимков, ${events.length} событий, фокусы ${meta.slice.foci}`);
console.log(`       события ${meta.slice.n_events_before} -> ${meta.slice.n_events_after}, ` +
            `рёбра known ${meta.slice.known_edges_before} -> ${meta.slice.known_edges_after}`);

for (const FOCUS of meta.slice.foci) {
  const e = cards.entries[String(FOCUS)];
  if (!e) { fail(`cards.json не несёт #${FOCUS}`); continue; }
  if (!e.arc) fail(`#${FOCUS}: пустая дуга`);
  if (!(e.arc_evidence || []).length) fail(`#${FOCUS}: ярлык без подкрепления (D4)`);
  if (!e.narrative) fail(`#${FOCUS}: пустой нарратив`);

  // the front reads these two on EVERY repaint — they must resolve on every tick
  let ticksOwning = 0, ticksAlive = 0;
  for (const B of snaps) {
    if (!Array.isArray(B.owners)) { fail(`t=${B.t}: нет owners`); break; }
    if (!Array.isArray(B.pawns)) { fail(`t=${B.t}: нет pawns`); break; }
    const cells = B.owners.filter((o) => o[2] === FOCUS);
    const here = B.pawns.find((p) => p[0] === FOCUS);
    if (cells.length) ticksOwning++;
    if (here) {
      ticksAlive++;
      if (!(here[1] >= 0 && here[1] < meta.grid_rows && here[2] >= 0 && here[2] < meta.grid_cols)) {
        fail(`t=${B.t}: #${FOCUS} вне сетки (${here[1]},${here[2]})`);
      }
    }
  }
  // the card's own numbers must agree with what the map will show, or the panel and the
  // outline would tell two different stories about the same pawn
  const pr = e.card.property;
  const okTicks = ticksOwning === pr.ticks_holding;
  if (!okTicks) fail(`#${FOCUS}: тиков с землёй по снимкам ${ticksOwning} != карточка ${pr.ticks_holding}`);
  console.log(`  #${FOCUS} «${e.arc}»  чипов подкрепления ${e.arc_evidence.length}  ` +
              `тиков с землёй ${ticksOwning} == карточка ${pr.ticks_holding} ${okTicks ? "✓" : "✗"}  ` +
              `жива на ${ticksAlive} тиках`);
}

// ---- Ф2: the flow index the arrows are drawn from ------------------------ //
// The front builds this from cards.json (never re-deriving the extortion split in JS), so the
// fields it reaches for must exist and every counterpart must be findable on the map at that
// same tick — otherwise an arrow would point at nothing, or worse, silently not be drawn.
for (const FOCUS of meta.slice.foci) {
  const P = cards.entries[String(FOCUS)].card.power;
  const snapAt = new Map(snaps.map((s) => [s.t, s]));
  const rows = [];
  for (const [role, rs, others] of [
    ["paid", P.paid, "to"], ["got", P.received, "from"],
    ["took", P.extorted, "victims"], ["lost", P.extorted_by, "takers"],
    ["remit", P.remitted, "to_root"], ["recv", P.received_remit, "from"],
  ]) {
    for (const r of rs) {
      const o = r[others];
      rows.push({ role, t: r.t, mass: r.mass !== undefined ? r.mass : r.share,
                  others: Array.isArray(o) ? o : [o] });
    }
  }
  let unresolved = 0, missingSelf = 0, nullMass = 0, drawn = 0;
  for (const r of rows) {
    const B = snapAt.get(r.t);
    if (!B) { unresolved++; continue; }
    if (!B.pawns.find((p) => p[0] === FOCUS)) missingSelf++;
    if (r.mass === null || r.mass === undefined) nullMass++;
    for (const o of r.others) {
      if (o === null || o === undefined) continue;
      if (B.pawns.find((p) => p[0] === o)) drawn++; else unresolved++;
    }
  }
  const ok = unresolved === 0 && missingSelf === 0;
  if (!ok) fail(`#${FOCUS}: потоки — неразрешимых контрагентов ${unresolved}, ` +
                `тиков без самой пешки ${missingSelf}`);
  const T = P.totals;
  console.log(`  #${FOCUS} потоки: ${rows.length} строк, ${drawn} стрелок разрешено, ` +
              `контрагентов не найдено ${unresolved} ${ok ? "✓" : "✗"}`);
  console.log(`        рисуется ПРИПИСАННОЕ ${T.extort_attributed} кг ` +
              `(брутто по тем же событиям ${T.extort_gross}), нетто ${T.net}` +
              (nullMass ? `; строк с неразрешимой долей ${nullMass} (рисуются без числа)` : ""));
}

// ---- Track B: the one-tick contract of the focus layer, as a STANDING test ---- //
// Bug #81 was found by eye, not by a gate: `updateFocus()` read `S.snaps[S.idx]` while the map
// drew `curSnaps()[1]` — outline, arrows and caption belonged to different ticks. The package
// gates could not see it by construction: they validate DATA, never the front's choice of tick.
//
// WHAT THIS TEST CAN AND CANNOT DO. Node has no DOM and no canvas, so pixels stay out of reach
// — that boundary is unchanged and is stated, not worked around. But the tick SELECTION is pure
// logic over {idx, snaps, frac}, so it is extracted from the page source and executed here for
// real. Two layers:
//   (a) DYNAMIC — `curSnaps`/`displayTick` are evaluated against a synthetic S, and the guard's
//       own condition (panel tick == map tick) is replayed over every index including the hero
//       ticks. This is the runtime guard `S._syncBroken`, run in CI instead of by eye.
//   (b) STRUCTURAL — the focus-layer consumers must take their snapshot from `curSnaps()`; a
//       raw `S.snaps[S.idx]` inside any of them is the exact shape of #81 and fails here.
const HTML = readFileSync(join(HERE, "..", "glass", "index.html"), "utf8");
const SRC = [...HTML.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join("\n");

function fnBody(name) {
  const i = SRC.indexOf(`function ${name}(`);
  if (i < 0) return null;
  let d = 0, started = false;
  for (let k = SRC.indexOf("{", i); k < SRC.length; k++) {
    if (SRC[k] === "{") { d++; started = true; }
    else if (SRC[k] === "}") { d--; if (started && d === 0) return SRC.slice(i, k + 1); }
  }
  return null;
}

// (a) dynamic — the tick math, executed
const curSrc = fnBody("curSnaps"), dispSrc = fnBody("displayTick");
if (!curSrc || !dispSrc) fail("в index.html не найдены curSnaps/displayTick — тест устарел");
else {
  const mk = new Function("S", `${curSrc}\n${dispSrc}\nreturn {curSnaps, displayTick};`);
  const fakeSnaps = snaps.map((s) => ({ t: s.t }));
  let bad = 0, checked = 0;
  for (let idx = 0; idx < fakeSnaps.length; idx++) {
    const S = { idx, snaps: fakeSnaps, frac: 0 };
    const { curSnaps, displayTick } = mk(S);
    // this IS the guard from updateFocus(): the panel's snapshot vs the film's tick
    const panelTick = curSnaps()[1].t;
    checked++;
    if (panelTick !== displayTick()) bad++;
  }
  if (bad) fail(`тик панели != тик карты на ${bad} из ${checked} позиций скраба`);
  else console.log(`  один тик на всех ${checked} позициях скраба ✓ (страж S._syncBroken не встал)`);
  // and explicitly at the hero ticks named in the WO
  const HERO = [12, 13, 14, 168, 252, 321, 322];
  const missed = HERO.filter((T) => {
    const idx = fakeSnaps.findIndex((s) => s.t === T) - 1;
    if (idx < 0) return false;
    const S = { idx, snaps: fakeSnaps, frac: 0 };
    const { curSnaps, displayTick } = mk(S);
    return curSnaps()[1].t !== T || displayTick() !== T;
  });
  if (missed.length) fail(`геройские тики разошлись: ${missed}`);
  else console.log(`  геройские тики ${HERO.join(", ")} — карта и панель совпали ✓`);
}

// (a2) SEEK TRUTH — `seek(T)` must never show a tick LATER than T.
// The master scrubber (split.html, and the E3 diptych) drives panes with {cmd:'seek',t}. Until
// the front-truth fix, `seekTick` aimed at the snapshot whose t == T while the film draws
// snaps[idx+1] — so the master's label said T and the pane showed T+1 (measured at
// t=14/100/321/322). Both panes shifted alike, so cross-pane sync survived; what lied was the
// TIME. Same class as #81, one level up. Locked here so it cannot come back quietly.
//
// THE INVARIANT IS "<=", NOT "==" — and that correction came from testing against β-3 rather
// than from reasoning. β-3 packages are exported sparsely (--every K), so the nearest snapshot
// at-or-before T can be genuinely earlier: there seek(20) lands on 18 and seek(100) on 99, and
// that is CORRECT. What is never correct is landing LATER than asked — the old behaviour. So
// the gate asserts `shown <= T` and `shown` is the greatest available tick <= T. The slice
// package is dense (every=1), so for it this reduces to equality and is reported as such.
const seekSrc = fnBody("seekTick");
if (!seekSrc) fail("в index.html не найден seekTick — тест устарел");
else if (curSrc && dispSrc) {
  const mkSeek = new Function("$", "S",
    `${curSrc}
${dispSrc}
${seekSrc}
return {curSnaps, displayTick, seekTick};`);
  const fakeSnaps = snaps.map((s) => ({ t: s.t }));
  const noDom = () => null;              // seekTick reaches the DOM only through $()
  const off = [];
  for (const T of fakeSnaps.map((s) => s.t)) {
    const S = { idx: 0, snaps: fakeSnaps, frac: 0, playing: false };
    const api = mkSeek(noDom, S);
    api.seekTick(T);
    // the film always draws B = snaps[idx+1], so the first tick is unreachable by
    // construction; it is not counted against the invariant, and that is said, not hidden
    const shown = api.displayTick();
    // greatest available tick <= T; for a dense package that is T itself
    const want = Math.max(...fakeSnaps.map((s) => s.t).filter((x) => x <= T));
    if (T > fakeSnaps[0].t && shown !== want) off.push(`${T}->${shown} (ждали ${want})`);
  }
  if (off.length) fail(`seek(T) промахивается: ${off.slice(0, 6).join(", ")} (всего ${off.length})`);
  else console.log(`  seek(T) -> наибольший доступный тик <= T, на всех ` +
                   `${fakeSnaps.length - 1} тиках ✓ (пакет плотный, значит ровно T)`);
}

// (a3) EMBED — the parameter must be READ, not merely promised in a comment. It sat in main
// since β-3 as a comment only: split.html passed embed=1 into both iframes and nothing read it.
// A comment describing a feature nobody implemented is worse than no comment — it is a claim
// the reader has no reason to doubt.
if (!/get\("embed"\)/.test(SRC)) fail("embed=1 не читается кодом — комментарий обещает несуществующее");
else console.log("  embed=1 читается кодом, не только комментарием ✓");

// (b) structural — every focus-layer consumer must derive its snapshot from curSnaps().
// The consumer list is DERIVED, not hard-coded: anything that mentions FOCUS is a focus-layer
// function by definition, so a NEW consumer added later is covered automatically. A fixed list
// would quietly stop guarding the moment someone adds the fifth reader — the same "green on
// emptiness" shape this whole test exists to prevent.
const consumers = [...SRC.matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\(/g)]
  .map((m) => m[1])
  .filter((n) => { const b = fnBody(n); return b && /\bFOCUS\b/.test(b); });
if (!consumers.length) fail("не найдено ни одной функции, читающей FOCUS — фокус-слой исчез?");
else console.log(`  потребителей фокус-слоя выведено: ${consumers.join(", ")}`);
for (const name of consumers) {
  if (/S\.snaps\s*\[\s*S\.idx\s*\]/.test(fnBody(name))) {
    fail(`${name} читает S.snaps[S.idx] напрямую — это ровно форма бага #81`);
  }
}
if (!/S\._syncBroken/.test(SRC)) fail("рантайм-страж S._syncBroken пропал из index.html");
else console.log("  рантайм-страж S._syncBroken на месте ✓");

// ---- E3 DIPTYCH-SYNC — the wiring of the two-pane view ------------------------ //
// A diptych's entire claim is "these two things at the SAME instant". The data half of that is
// already gated above (both foci resolve at every tick, from one package). What remains is the
// WIRING, and wiring is where it actually broke while this was being built: the pane iframes
// are rooted at /glass/, so a data path written relative to the diptych page resolves against
// the WRONG directory inside them and 404s in silence — the pane just sits on its drop-zone.
// Caught by loading it, not by reading it; locked here so the next author does not re-lose it.
const DIP = join(HERE, "..", "diptych.html");
let dipSrc = null;
try { dipSrc = readFileSync(DIP, "utf8"); } catch (e) { dipSrc = null; }
if (dipSrc === null) console.log("  diptych.html отсутствует — DIPTYCH-SYNC пропущен (ещё не построен)");
else {
  const srcs = [...dipSrc.matchAll(/\.src\s*=\s*`([^`]+)`/g)].map((m) => m[1]);
  if (srcs.length !== 2) fail(`diptych: ожидалось 2 панели, найдено ${srcs.length}`);
  else {
    const dataOf = (u) => (u.match(/data=\$\{encodeURIComponent\((\w+)\)\}/) || [])[1];
    const focusOf = (u) => (u.match(/focus=\$\{(\w+)\}/) || [])[1];
    if (dataOf(srcs[0]) !== dataOf(srcs[1]))
      fail("diptych: панели грузят РАЗНЫЕ пакеты — «один тик» тогда ничего не значит");
    else console.log(`  обе панели над ОДНИМ пакетом (${dataOf(srcs[0])}) ✓`);
    // the path handed to a pane must be pane-relative, or it 404s inside the iframe
    const paneVar = dataOf(srcs[0]);
    // NB: template literal — `\s` would be eaten by JS before RegExp ever sees it, so the
    // backslashes are doubled. The gate caught its own broken pattern by failing LOUDLY
    // ("путь ... undefined") instead of quietly matching nothing and passing.
    const decl = (dipSrc.match(new RegExp(`const\\s+${paneVar}\\s*=\\s*"([^"]+)"`)) || [])[1];
    if (!decl || !decl.startsWith("../"))
      fail(`diptych: путь для панелей "${decl}" не относителен ПАНЕЛИ — внутри iframe он 404-ит молча`);
    else console.log(`  путь панелей относителен панели ("${decl}") ✓`);
    if (!srcs.every((u) => /embed=1/.test(u)))
      fail("diptych: панель без embed=1 — мастер и панель будут дублировать контролы");
    else console.log("  обе панели с embed=1 ✓");
    const foci = srcs.map((u) => focusOf(u));
    if (foci.some((f) => !f)) fail("diptych: фокус панели не разобран");
  }
  // the master must drive BOTH panes; a seek that reaches one pane is a diptych that lies
  const seekFn = (dipSrc.match(/function seek\([\s\S]*?[\r\n]\}/) || [])[0] || "";
  const posts = (seekFn.match(/postMessage/g) || []).length;
  const loopsBoth = /\[\s*fa\s*,\s*fb\s*\]/.test(seekFn);
  if (!posts || !loopsBoth)
    fail("diptych: seek() не рассылает {cmd:'seek'} обеим панелям");
  else console.log("  мастер-скраб адресует ОБЕ панели ✓");
  // and it must not grow a per-pane scrub: two scrubs are two timelines
  if (/id="scrub"/.test(dipSrc) && (dipSrc.match(/id="scrub"/g) || []).length > 1)
    fail("diptych: больше одного скраба — два таймлайна вместо одного");
}

// the caption layer of Ф3 will read events by tick; prove the index is dense and sorted
let prev = -1, unsorted = 0;
for (const ev of events) { if (ev.t < prev) unsorted++; prev = ev.t; }
if (unsorted) fail(`события не отсортированы по t (${unsorted} инверсий)`);
else console.log(`  события монотонны по t ✓ (t от ${events[0].t} до ${events[events.length - 1].t})`);

console.log("=".repeat(78));
if (bad) { console.log(`КОНТРАКТ ФРОНТА НАРУШЕН: ${bad} провал(ов)`); process.exit(1); }
console.log("контракт фронта цел: фокус, владение, карточка и подкрепление читаются на каждом тике ✓");
console.log("(холст headless не проверяется — это контракт данных, не рендер)");
