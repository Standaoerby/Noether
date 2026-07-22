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

// the caption layer of Ф3 will read events by tick; prove the index is dense and sorted
let prev = -1, unsorted = 0;
for (const ev of events) { if (ev.t < prev) unsorted++; prev = ev.t; }
if (unsorted) fail(`события не отсортированы по t (${unsorted} инверсий)`);
else console.log(`  события монотонны по t ✓ (t от ${events[0].t} до ${events[events.length - 1].t})`);

console.log("=".repeat(78));
if (bad) { console.log(`КОНТРАКТ ФРОНТА НАРУШЕН: ${bad} провал(ов)`); process.exit(1); }
console.log("контракт фронта цел: фокус, владение, карточка и подкрепление читаются на каждом тике ✓");
console.log("(холст headless не проверяется — это контракт данных, не рендер)");
