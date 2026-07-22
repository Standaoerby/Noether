"""export_slice_figure.py — E2 Ф3: the pawn slice as a SELF-CONTAINED artifact.

Symmetrical to E1's `pawn_<oid>.html`: one file, inline CSS/JS, no network, nothing to serve —
for the book and for sharing. Canon-free at read time (it is plain data + a small renderer),
and canon-free at build time in the same sense every reader in this axis is: it runs the
exporter, never the mechanics.

WHAT GOES IN, AND WHY NOT THE PACKAGE. The slice package is 10.4 MB because it carries the
whole colony — 945 pawns per snapshot, the global ownership ledger, every flow. A shareable
figure does not need the colony; it needs ONE pawn's story. So the artifact embeds only the
focus's own trace: its position per tick, its estate per tick, the flows touching it, and the
captions. That is ~100× smaller and says the same thing about the same pawn.

The captions are NOT re-composed here — they are copied verbatim from `event_captions`, the
same projection the in-app view reads, so the file and the app can never tell two stories.

Run:  py stage3/export_slice_figure.py            # #58 and #42
      py stage3/export_slice_figure.py --oids 58
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Code"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stage3.export_pawn_card import e1_scene                              # noqa: E402
from stage3.viz_export import run_capture, _dumps                         # noqa: E402
from stage3.pawn_card import (pawn_card, narrate_card, _arc_of,           # noqa: E402
                              arc_evidence, event_captions)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(ROOT, "viz", "figures")
DEFAULT_OIDS = (58, 42)
ARROW_CAP = 10          # same self-declaring cap as the in-app view


def build_trace(w, snaps, oid):
    """Everything the figure draws about ONE pawn — and nothing about the other 944."""
    card = pawn_card(w.log, snaps, oid)
    P = card["power"]
    pos, estate = {}, {}
    for s in snaps:
        p = next((q for q in s["pawns"] if q[0] == oid), None)
        if p is not None:
            pos[s["t"]] = [p[1], p[2], round(float(p[3]), 3)]
        cells = [[i, j] for (i, j, o) in s["owners"] if o == oid]
        if cells:
            estate[s["t"]] = cells
    flows = {}
    for role, rows, key, mass in (("paid", P["paid"], "to", "mass"),
                                  ("got", P["received"], "from", "mass"),
                                  ("took", P["extorted"], "victims", "share"),
                                  ("lost", P["extorted_by"], "takers", "gross"),
                                  ("remit", P["remitted"], "to_root", "mass"),
                                  ("recv", P["received_remit"], "from", "mass")):
        for r in rows:
            others = r[key]
            others = others if isinstance(others, list) else [others]
            hidden = max(0, len(others) - ARROW_CAP)
            flows.setdefault(r["t"], []).append(
                {"role": role, "m": r.get(mass), "o": sorted(others)[:ARROW_CAP],
                 "hidden": hidden})
    caps = event_captions(w.log, oid)
    return {
        "oid": oid, "arc": _arc_of(card), "evidence": arc_evidence(card),
        "narrative": narrate_card(card), "captions": caps,
        "sha": card["sha"], "card_version": card["card_version"],
        "totals": P["totals"], "roles": P["roles"], "coincidence": P["coincidence"],
        "pos": pos, "estate": estate, "flows": flows,
        "rows": int(w.soil.shape[0]), "cols": int(w.soil.shape[1]),
        "t_end": caps["t_end"],
    }


_CSS = """
:root{--ink:#e8e8ee;--dim:#9a9aa6;--line:#33333d;--acc:#e0857f;--gold:#ffcf5d;
--red:#ff5d6c;--blue:#7fb2ff;--bg:#0e0f13;--panel:#181a20}
@media(prefers-color-scheme:light){:root{--ink:#1b1b1f;--dim:#6b6b76;--line:#d8d8e0;
--acc:#8a2f2f;--gold:#a97b1a;--red:#b3303c;--blue:#2f5fa8;--bg:#faf9f7;--panel:#fff}}
*{box-sizing:border-box}body{margin:0;padding:2rem 1rem;background:var(--bg);color:var(--ink);
font:16px/1.6 Georgia,'Times New Roman',serif}
.wrap{max-width:60rem;margin:0 auto}
h1{font-size:1.6rem;margin:0 0 .2rem}
.arc{display:inline-block;font:600 .72rem/1 system-ui,sans-serif;letter-spacing:.08em;
text-transform:uppercase;color:var(--acc);border:1px solid var(--acc);border-radius:2rem;
padding:.35rem .7rem}
.why{display:flex;flex-wrap:wrap;gap:.3rem;margin:.6rem 0 1rem}
.chip{font:.74rem/1.5 system-ui,sans-serif;color:var(--dim);background:var(--panel);
border:1px solid var(--line);border-radius:1rem;padding:.1rem .6rem}
.chip b{color:var(--ink);font-variant-numeric:tabular-nums}
.stage{display:grid;grid-template-columns:minmax(260px,380px) 1fr;gap:1rem;align-items:start}
@media(max-width:760px){.stage{grid-template-columns:1fr}}
canvas{width:100%;height:auto;background:var(--panel);border:1px solid var(--line);
border-radius:.3rem;display:block}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:.3rem;padding:.8rem .9rem}
.thesis{font-style:italic;color:var(--gold);margin:0 0 .6rem}
.beat{border-left:2px solid var(--red);padding-left:.6rem;margin:.35rem 0;
font:.9rem/1.5 system-ui,sans-serif}
.beat.past{border-color:var(--line);opacity:.5}
.ctl{display:flex;gap:.5rem;align-items:center;margin:.8rem 0}
.ctl input[type=range]{flex:1}
button{font:inherit;font-size:.85rem;padding:.2rem .7rem;background:var(--panel);
color:var(--ink);border:1px solid var(--line);border-radius:.25rem;cursor:pointer}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:.1rem .8rem;
font:.82rem/1.5 system-ui,sans-serif}
dt{color:var(--dim)}dd{margin:0;text-align:right;font-variant-numeric:tabular-nums}
footer{margin-top:1.4rem;color:var(--dim);font:.75rem/1.5 system-ui,sans-serif;
border-top:1px solid var(--line);padding-top:.6rem}
code{font:.8rem ui-monospace,monospace;color:var(--dim)}
"""

_JS = r"""
const D=DATA, N=D.rows, M=D.cols;
const cv=document.getElementById("map"), cx=cv.getContext("2d");
const sc=document.getElementById("scrub"), tl=document.getElementById("tlab");
const beats=document.getElementById("beats"), flow=document.getElementById("flow");
let T=1, playing=false;
const COL={paid:"#7fb2ff",got:"#7fb2ff",took:"#ff5d6c",lost:"#ff5d6c",
           remit:"#ffcf5d",recv:"#ffcf5d"};
const LAB={paid:"платит ренту",got:"получает ренту",took:"отнимает силой",
           lost:"у неё отнимают",remit:"отдаёт наверх",recv:"принимает снизу"};
const SIGN={paid:-1,got:1,took:1,lost:-1,remit:-1,recv:1};
function draw(){
  const S=cv.width/M;
  cx.clearRect(0,0,cv.width,cv.height);
  cx.strokeStyle="#33333d"; cx.lineWidth=1;
  for(let i=0;i<=N;i++){cx.beginPath();cx.moveTo(0,i*S);cx.lineTo(cv.width,i*S);cx.stroke();}
  for(let j=0;j<=M;j++){cx.beginPath();cx.moveTo(j*S,0);cx.lineTo(j*S,cv.height);cx.stroke();}
  // trail: where she has been up to now
  cx.strokeStyle="#ffcf5d"; cx.globalAlpha=.18; cx.lineWidth=2; cx.beginPath();
  let started=false;
  for(let t=1;t<=T;t++){const p=D.pos[t]; if(!p)continue;
    const x=(p[1]+.5)*S,y=(p[0]+.5)*S; started?cx.lineTo(x,y):cx.moveTo(x,y); started=true;}
  cx.stroke(); cx.globalAlpha=1;
  // estate at THIS tick
  const est=D.estate[T]||[];
  cx.strokeStyle="#ffcf5d"; cx.lineWidth=2; cx.setLineDash([5,4]);
  for(const [i,j] of est) cx.strokeRect(j*S+2,i*S+2,S-4,S-4);
  cx.setLineDash([]);
  // the pawn
  const p=D.pos[T];
  if(p){
    const x=(p[1]+.5)*S,y=(p[0]+.5)*S,r=Math.max(4,Math.min(S*.32,3+p[2]*7));
    cx.beginPath();cx.arc(x,y,r,0,7);cx.fillStyle="#e0857f";cx.fill();
    cx.beginPath();cx.arc(x,y,r+5,0,7);cx.strokeStyle="#ffcf5d";cx.lineWidth=2.5;cx.stroke();
  }else{
    cx.fillStyle="#9a9aa6";cx.font="14px system-ui";
    cx.fillText(T<=1?"ещё не появилась":"её больше нет",10,20);
  }
  // captions at this tick (frame stays above; these are the beats)
  const now=D.captions.items.filter(c=>c.t===T);
  const past=D.captions.items.filter(c=>c.t<T);
  let h="";
  for(const c of now) h+='<div class="beat"><b>t='+c.t+'</b> '+c.text+'</div>';
  if(!now.length&&past.length){const c=past[past.length-1];
    h='<div class="beat past"><b>t='+c.t+'</b> '+c.text+'</div>';}
  if(!h) h='<div class="beat past">— пока ничего не случилось</div>';
  beats.innerHTML=h;
  // flows at this tick — attributed mass, never the pooled gross
  const fr=D.flows[T]||[]; let fh="";
  let hid=0;
  for(const f of fr){ hid+=f.hidden;
    const m=(f.m===null||f.m===undefined)?"—":(SIGN[f.role]>0?"+":"−")+Math.abs(f.m).toFixed(4);
    fh+='<div style="color:'+COL[f.role]+'">'+LAB[f.role]+" "+m+" кг · "
      + f.o.map(o=>"#"+o).join(", ")+(f.hidden?" и ещё "+f.hidden:"")+"</div>";
  }
  flow.innerHTML=fh||'<div style="opacity:.5">нет потоков в этот день</div>';
  tl.textContent="день "+T+" из "+D.t_end;
  sc.value=T;
}
sc.oninput=()=>{T=+sc.value; draw();};
document.getElementById("bPlay").onclick=function(){
  playing=!playing; this.textContent=playing?"пауза":"играть";
  const step=()=>{ if(!playing)return; T=T>=D.t_end?1:T+1; draw(); setTimeout(step,60); };
  step();
};
document.getElementById("bPrev").onclick=()=>{playing=false;T=Math.max(1,T-1);draw();};
document.getElementById("bNext").onclick=()=>{playing=false;T=Math.min(D.t_end,T+1);draw();};
// jump straight to the beats
document.getElementById("jump").onchange=function(){
  playing=false; T=+this.value; draw();
};
draw();
"""


def render(trace):
    e = trace
    chips = "".join(f'<span class="chip">{html.escape(str(k))}: <b>{html.escape(str(v))}</b></span>'
                    for k, v in e["evidence"])
    thesis = next((l for l in e["narrative"].split("\n") if l.startswith("Тезис:")), "")
    T = e["totals"]
    opts = "".join(f'<option value="{c["t"]}">t={c["t"]} — {html.escape(c["text"][:60])}</option>'
                   for c in e["captions"]["items"])
    facts = "".join(
        f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in [
            ("рента получена, кг", T["rent_received"]),
            ("рента уплачена, кг", T["rent_paid"]),
            ("изъятий с её участием", e["roles"]["extort"]["taker"]),
            ("· брутто по ним, кг", T["extort_gross"]),
            ("· приписано ей, кг", T["extort_attributed"]),
            ("итого по властным потокам, кг", T["net"]),
        ])
    return f"""<meta charset="utf-8">
<title>Слайс пешки #{e['oid']} — {html.escape(e['arc'])}</title>
<style>{_CSS}</style>
<div class="wrap">
<h1>Пешка #{e['oid']}</h1>
<div class="arc">{html.escape(e['arc'])}</div>
<div class="why">{chips}</div>
<p class="thesis">{html.escape(thesis)}</p>
<div class="stage">
  <div>
    <canvas id="map" width="380" height="380"></canvas>
    <div class="ctl">
      <button id="bPrev">←</button><button id="bPlay">играть</button><button id="bNext">→</button>
      <span id="tlab" style="font:.8rem system-ui;color:var(--dim)"></span>
    </div>
    <input id="scrub" type="range" min="1" max="{e['t_end']}" value="1" style="width:100%">
    <div class="ctl"><select id="jump" style="width:100%;font:.78rem system-ui">
      <option value="1">— перейти к событию —</option>{opts}</select></div>
  </div>
  <div>
    <div class="panel"><div id="beats"></div></div>
    <div class="panel" style="margin-top:.7rem;font:.85rem/1.6 ui-monospace,monospace">
      <div id="flow"></div></div>
    <div class="panel" style="margin-top:.7rem"><dl>{facts}</dl></div>
    <details class="panel" style="margin-top:.7rem"><summary style="cursor:pointer">вся дуга</summary>
      <div style="white-space:pre-wrap;font:.86rem/1.6 system-ui,sans-serif;margin-top:.5rem">{html.escape(e['narrative'])}</div>
    </details>
  </div>
</div>
<footer>Noether · E2 слайс пешки · карточка v{e['card_version']} · <code>sha {e['sha']}</code><br>
Подписи — проекция тех же событий, что рисует карта (гейт E2-HONEST: каждая врезка
подкреплена событием того же тика). Масса у потока — <b>приписанная</b> доля, не брутто пула.
Свёрнуто потоков-событий: {e['captions']['flow_folded']} из {e['captions']['flow_events']}
(правило: {html.escape(e['captions']['rule'])}).</footer>
</div>
<script>const DATA={_dumps(trace)};{_JS}</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oids", type=str, default=",".join(str(o) for o in DEFAULT_OIDS))
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--days", type=int, default=400)
    args = ap.parse_args()
    oids = [int(x) for x in args.oids.split(",") if x.strip()]
    w, snaps = run_capture(e1_scene(seed=args.seed, days=args.days), 1)
    os.makedirs(FIG_DIR, exist_ok=True)
    for oid in oids:
        tr = build_trace(w, snaps, oid)
        out = os.path.join(FIG_DIR, f"slice_{oid}.html")
        blob = render(tr)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(blob)
        print(f"слайс #{oid} ({tr['arc']}) -> {os.path.relpath(out, ROOT)}  "
              f"{len(blob.encode('utf-8'))/1e3:.0f} КБ  врезок {tr['captions']['n']}  "
              f"sha карточки {tr['sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
