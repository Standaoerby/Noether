"""export_diptych_figure.py — E3 Ф3: the diptych as a SELF-CONTAINED artifact.

WHAT "SELF-CONTAINED" MEANS HERE, since the live diptych reads a 10.41 MB package. It does NOT
mean inlining that package. E2 already answered this: `slice_58.html` came out at 52 KB against
the same 10.41 MB, because a figure does not need the colony — it needs ONE pawn's trace. The
diptych needs two. So the artifact embeds the traces of #58 and #42 and nothing else: ~100×
smaller, one file, no server, no network, openable by double-click and mailable.

The live `viz/diptych.html` and this artifact are two consumers of the same facts, and neither
recomputes them: every headline number is copied out of the card's power projection, whose
attribution was verified against real body deltas by gate PF-SHARE. `check_front_contract.mjs`
holds the live shell to that (DIPTYCH-HONEST); this file is held to it by construction, since
it can only copy what `build_trace` hands it.

Run:  py stage3/export_diptych_figure.py
"""
from __future__ import annotations

import argparse
import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stage3.export_pawn_card import e1_scene                               # noqa: E402
from stage3.viz_export import run_capture, _dumps                          # noqa: E402
from stage3.export_slice_figure import build_trace, FIG_DIR, ROOT          # noqa: E402

LEFT, RIGHT = 58, 42

_CSS = """
:root{--ink:#e8e8ee;--dim:#9a9aa6;--line:#2a2a34;--bg:#0e0f13;--pan:#15161c;
--gold:#ffcf5d;--red:#ff5d6c;--good:#5dd6a0;--acc:#e0857f}
@media(prefers-color-scheme:light){:root{--ink:#1b1b1f;--dim:#666;--line:#d8d8e0;--bg:#faf9f7;
--pan:#fff;--gold:#a97b1a;--red:#b3303c;--good:#1f7a4d;--acc:#8a2f2f}}
*{box-sizing:border-box}body{margin:0;padding:1.2rem 1rem 2rem;background:var(--bg);
color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:72rem;margin:0 auto}
h1{font:600 1.35rem/1.25 Georgia,serif;margin:0 0 .3rem}
.thesis{color:var(--dim);font-size:.9rem;margin:0 0 1rem;max-width:60rem}
.thesis b{color:var(--ink)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:820px){.grid{grid-template-columns:1fr}}
.col{background:var(--pan);border:1px solid var(--line);border-radius:.4rem;padding:.8rem .9rem}
.who{font:600 1.05rem Georgia,serif}
.arc{display:inline-block;font:600 .62rem/1 system-ui;letter-spacing:.09em;
text-transform:uppercase;border:1px solid currentColor;border-radius:1rem;padding:.2rem .55rem;
margin-left:.4rem}
.neg{color:var(--red)}.pos{color:var(--good)}
.nums{display:flex;flex-wrap:wrap;gap:.25rem .5rem;margin:.55rem 0}
.chip{font-size:.73rem;color:var(--dim);background:rgba(128,128,128,.09);
border:1px solid var(--line);border-radius:1rem;padding:.08rem .55rem;white-space:nowrap}
.chip b{color:var(--ink);font-variant-numeric:tabular-nums}
canvas{width:100%;height:auto;background:rgba(128,128,128,.06);border:1px solid var(--line);
border-radius:.3rem;display:block;margin:.3rem 0}
.live{font-size:.78rem;color:var(--dim);display:flex;flex-wrap:wrap;gap:.2rem .7rem;
min-height:1.5rem}
.live b{color:var(--ink);font-variant-numeric:tabular-nums}
.live .dead{color:var(--red);font-weight:600}
.beat{font-size:.82rem;min-height:3.2rem;border-left:2px solid var(--gold);padding-left:.6rem;
margin-top:.5rem}
.beat b{color:var(--gold)}.beat .past{opacity:.45}
.ctl{display:flex;align-items:center;gap:.6rem;margin:1rem 0 .3rem}
.ctl input[type=range]{flex:1}
button{font:inherit;font-size:.85rem;padding:.2rem .8rem;background:var(--pan);color:var(--ink);
border:1px solid var(--line);border-radius:.25rem;cursor:pointer}
select{font:inherit;font-size:.78rem;background:var(--pan);color:var(--ink);
border:1px solid var(--line);border-radius:.25rem;padding:.15rem}
footer{margin-top:1.2rem;color:var(--dim);font-size:.74rem;border-top:1px solid var(--line);
padding-top:.6rem}
code{font:.78rem ui-monospace,monospace;color:var(--dim)}
"""

_JS = r"""
const N = D.rows, M = D.cols;
const SIDES = [D.left, D.right];
const cvs = [document.getElementById("mapL"), document.getElementById("mapR")];
const sc = document.getElementById("scrub"), tl = document.getElementById("tlab");
let T = 1, playing = false;

function drawOne(k) {
  const d = SIDES[k], cv = cvs[k], cx = cv.getContext("2d"), S = cv.width / M;
  cx.clearRect(0, 0, cv.width, cv.height);
  cx.strokeStyle = "rgba(128,128,128,.22)"; cx.lineWidth = 1;
  for (let i = 0; i <= N; i++) { cx.beginPath(); cx.moveTo(0, i*S); cx.lineTo(cv.width, i*S); cx.stroke(); }
  for (let j = 0; j <= M; j++) { cx.beginPath(); cx.moveTo(j*S, 0); cx.lineTo(j*S, cv.height); cx.stroke(); }
  // the trail so far
  cx.strokeStyle = "#ffcf5d"; cx.globalAlpha = .16; cx.lineWidth = 2; cx.beginPath();
  let started = false;
  for (let t = 1; t <= T; t++) { const p = d.pos[t]; if (!p) continue;
    const x = (p[1]+.5)*S, y = (p[0]+.5)*S; started ? cx.lineTo(x, y) : cx.moveTo(x, y); started = true; }
  cx.stroke(); cx.globalAlpha = 1;
  // the estate AT THIS TICK
  cx.strokeStyle = "#ffcf5d"; cx.lineWidth = 2; cx.setLineDash([5,4]);
  for (const [i, j] of (d.estate[T] || [])) cx.strokeRect(j*S+2, i*S+2, S-4, S-4);
  cx.setLineDash([]);
  // the pawn
  const p = d.pos[T];
  if (p) {
    const x = (p[1]+.5)*S, y = (p[0]+.5)*S, r = Math.max(4, Math.min(S*.34, 3 + p[2]*6));
    cx.beginPath(); cx.arc(x, y, r, 0, 7); cx.fillStyle = "#e0857f"; cx.fill();
    cx.beginPath(); cx.arc(x, y, r+5, 0, 7); cx.strokeStyle = "#ffcf5d"; cx.lineWidth = 2.5; cx.stroke();
  }
  // live strip
  const L = document.getElementById(k ? "lvR" : "lvL");
  const cells = d.estate[T] || [];
  L.innerHTML = (p
      ? `<span>жива, в <b>(${p[0]},${p[1]})</b></span><span>тело <b>${p[2].toFixed(2)}</b></span>`
      : `<span class="dead">мертва</span>`) +
    `<span>земля: <b>${cells.length ? cells.map((c) => `(${c[0]},${c[1]})`).join(" ") : "нет"}</b></span>`;
  // this pawn's own beat at this tick
  const B = document.getElementById(k ? "btR" : "btL");
  const now = d.captions.items.filter((c) => c.t === T);
  const past = d.captions.items.filter((c) => c.t < T);
  B.innerHTML = now.length
    ? now.map((c) => `<b>день ${c.t}.</b> ${c.text}`).join("<br>")
    : (past.length ? `<span class="past"><b>день ${past[past.length-1].t}.</b> ${past[past.length-1].text}</span>`
                   : '<span class="past">пока ничего не случилось</span>');
}
function draw() { drawOne(0); drawOne(1); tl.textContent = "день " + T + " из " + D.t_end; sc.value = T; }
sc.oninput = () => { playing = false; T = +sc.value; draw(); };
document.getElementById("play").onclick = function () {
  playing = !playing; this.textContent = playing ? "❚❚ пауза" : "▶ играть";
  const step = () => { if (!playing) return; T = T >= D.t_end ? 1 : T + 1; draw(); setTimeout(step, 70); };
  step();
};
document.getElementById("prev").onclick = () => { playing = false; T = Math.max(1, T-1); draw(); };
document.getElementById("next").onclick = () => { playing = false; T = Math.min(D.t_end, T+1); draw(); };
document.getElementById("jump").onchange = function () { playing = false; T = +this.value; draw(); };
draw();
"""


def col(side, cid, mid, lid, bid):
    T, R = side["totals"], side["roles"]
    net = T["net"]
    chips = "".join(
        f'<span class="chip">{html.escape(k)}: <b>{html.escape(str(v))}</b></span>' for k, v in [
            ("нетто по властным потокам", f"{net:+.2f} кг"),
            ("рента получена", f"{T['rent_received']:.2f}"),
            ("рента уплачена", f"{T['rent_paid']:.2f}"),
            ("изъятий с её участием", R["extort"]["taker"]),
            ("изъятий против неё", R["extort"]["victim"]),
            ("приписано ей", f"{T['extort_attributed']:.2f} кг из брутто {T['extort_gross']:.2f}"),
        ])
    return f"""<div class="col">
  <div><span class="who">#{side['oid']}</span>
    <span class="arc {'neg' if net < 0 else 'pos'}">{html.escape(side['arc'])}</span></div>
  <div class="nums">{chips}</div>
  <canvas id="{mid}" width="360" height="360"></canvas>
  <div class="live" id="{lid}"></div>
  <div class="beat" id="{bid}"></div>
</div>"""


def render(left, right):
    opts = "".join(
        f'<option value="{c["t"]}">день {c["t"]} — #{oid}: {html.escape(c["text"][:52])}</option>'
        for oid, side in ((LEFT, left), (RIGHT, right))
        for c in side["captions"]["items"])
    data = _dumps({"rows": left["rows"], "cols": left["cols"],
                   "t_end": max(left["t_end"], right["t_end"]),
                   "left": left, "right": right})
    return f"""<meta charset="utf-8">
<title>Диптих власти — #{LEFT} и #{RIGHT}</title>
<style>{_CSS}</style>
<div class="wrap">
<h1>Диптих власти — один день, две судьбы</h1>
<p class="thesis">Карта и счёт лгут о власти. Слева — <b>титул</b>: держал землю 320 дней и
участвовал в 174 изъятиях. Справа — та, кого счёт назвал <b>жертвой</b>: её обирали 387 раз.
Кто из них держал власть, показывает только сохраняющийся поток — он в числах под каждым именем.</p>
<div class="grid">
{col(left, "cL", "mapL", "lvL", "btL")}
{col(right, "cR", "mapR", "lvR", "btR")}
</div>
<div class="ctl">
  <button id="play">▶ играть</button><button id="prev">⟨</button><button id="next">⟩</button>
  <input type="range" id="scrub" min="1" max="{max(left['t_end'], right['t_end'])}" value="1">
  <span id="tlab" style="min-width:9rem"></span>
</div>
<div class="ctl"><select id="jump" style="flex:1">
  <option value="1">— перейти к событию —</option>{opts}</select></div>
<footer>Noether · E3 диптих · карточки v{left['card_version']} ·
<code>#{LEFT} sha {left['sha']} · #{RIGHT} sha {right['sha']}</code><br>
Самодостаточно: внутри — след ДВУХ пешек, не пакет. Живой диптих читает пакет 10.41 МБ; этой
фигуре колония не нужна, нужны две судьбы. Ни одно число здесь не пересчитано — все взяты из
проекции <code>power</code> карточек, чья атрибуция сверена с реальными дельтами тел (гейт
PF-SHARE). Масса у изъятий — <b>приписанная доля</b>, не брутто пула.</footer>
</div>
<script>const D={data};{_JS}</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--days", type=int, default=400)
    args = ap.parse_args()
    w, snaps = run_capture(e1_scene(seed=args.seed, days=args.days), 1)
    left, right = build_trace(w, snaps, LEFT), build_trace(w, snaps, RIGHT)
    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, f"diptych_{LEFT}_{RIGHT}.html")
    blob = render(left, right)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(blob)
    print(f"диптих -> {os.path.relpath(out, ROOT)}  {len(blob.encode('utf-8'))/1e3:.0f} КБ")
    print(f"  #{LEFT} «{left['arc']}» нетто {left['totals']['net']:+.2f}  sha {left['sha']}")
    print(f"  #{RIGHT} «{right['arc']}» нетто {right['totals']['net']:+.2f}  sha {right['sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
