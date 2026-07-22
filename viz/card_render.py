"""card_render.py — E1: pure presentation for the pawn card.

Canon-free BY DESIGN: this module imports nothing from `Code/` or `stage3/`, so the viz
server can render a card without pulling the simulation into its process (the server's rule
is that nothing outside /run and /sweep touches Code/). It is pure string formatting over the
exported card dict, which is why the in-app view and the standalone artifact can share one
renderer and never drift apart.
"""
from __future__ import annotations

import html

CARD_VERSION = 1


_CSS = """
:root{--ink:#1b1b1f;--dim:#6b6b76;--line:#d8d8e0;--acc:#8a2f2f;--bg:#faf9f7;--panel:#fff}
@media(prefers-color-scheme:dark){:root{--ink:#e8e8ee;--dim:#9a9aa6;--line:#33333d;
--acc:#e0857f;--bg:#141418;--panel:#1c1c22}}
*{box-sizing:border-box}body{margin:0;padding:2rem 1rem;background:var(--bg);color:var(--ink);
font:16px/1.65 Georgia,'Times New Roman',serif}
.wrap{max-width:52rem;margin:0 auto}
h1{font-size:1.7rem;margin:0 0 .2rem;letter-spacing:-.01em}
.arc{display:inline-block;font:600 .72rem/1 system-ui,sans-serif;letter-spacing:.08em;
text-transform:uppercase;color:var(--acc);border:1px solid var(--acc);border-radius:2rem;
padding:.35rem .7rem;margin-bottom:1.2rem}
.narr{background:var(--panel);border-left:3px solid var(--acc);padding:1rem 1.2rem;
border-radius:.2rem;white-space:pre-wrap;margin:0 0 1.6rem}
.narr .thesis{font-style:italic;color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));gap:1rem}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:.3rem;padding:.9rem 1rem}
.panel h2{font:600 .74rem/1 system-ui,sans-serif;letter-spacing:.09em;text-transform:uppercase;
color:var(--dim);margin:0 0 .6rem}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:.15rem .8rem}
dt{color:var(--dim);font:400 .85rem/1.5 system-ui,sans-serif}
dd{margin:0;font-variant-numeric:tabular-nums;text-align:right}
.spark{width:100%;height:44px;display:block;margin-top:.6rem}
.wide{margin-top:1rem}
.note{margin:0 0 .8rem;color:var(--dim);font:.8rem/1.55 system-ui,sans-serif}
dt.sub{padding-left:1.1rem;font-style:italic}
dt.emph{color:var(--ink);font-weight:600}
footer{margin-top:1.6rem;color:var(--dim);font:.76rem/1.5 system-ui,sans-serif;
border-top:1px solid var(--line);padding-top:.7rem}
code{font:.8rem ui-monospace,monospace;color:var(--dim)}
"""


def _spark(series, w=520, h=44):
    """Inline SVG sparkline of the ownership series [[t, n_cells], ...]."""
    if not series:
        return '<p style="color:var(--dim)">земли не держала</p>'
    ts = [p[0] for p in series]
    vs = [p[1] for p in series]
    t0, t1 = min(ts), max(ts)
    vmax = max(vs) or 1
    span = (t1 - t0) or 1
    pts = " ".join(f"{(t - t0) / span * w:.1f},{h - (v / vmax) * (h - 6) - 3:.1f}"
                   for t, v in series)
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'role="img" aria-label="владение по тикам">'
            f'<polyline points="{pts}" fill="none" stroke="var(--acc)" stroke-width="2"/>'
            f'</svg>')


def _dl(pairs):
    """Rows are (label, value) or (label, value, css_class) — the class lets the power panel
    mark sub-rows and the bottom line without smuggling markup through the escaper."""
    out = []
    for row in pairs:
        k, v = row[0], row[1]
        cls = f' class="{row[2]}"' if len(row) > 2 else ""
        out.append(f"<dt{cls}>{html.escape(str(k))}</dt><dd>{html.escape(str(v))}</dd>")
    return "<dl>" + "".join(out) + "</dl>"


def render_html(entry, scene):
    card, narr, arc = entry["card"], entry["narrative"], entry["arc"]
    ch, ho, re_, pr = card["chronicle"], card["house"], card["relationships"], card["property"]
    rep, P = card["reputation"], card["power"]
    PR, PT, PC = P["roles"], P["totals"], P["coincidence"]
    t, oid = re_["totals"], card["oid"]
    # the narrative verbatim; only the thesis line gets a class for emphasis
    lines = []
    for ln in narr.splitlines():
        esc = html.escape(ln)
        lines.append(f'<span class="thesis">{esc}</span>' if ln.startswith("Тезис:") else esc)
    narr_html = "\n".join(lines)
    dth = ch["death"]
    body = f"""<div class="wrap">
<h1>Пешка #{oid}</h1>
<div class="arc">{html.escape(arc)}</div>
<div class="narr">{narr_html}</div>
<div class="grid">
  <div class="panel"><h2>Хроника</h2>{_dl([
      ("происхождение", (ch['origin'] or {}).get('kind', '—')),
      ("день рождения", (ch['origin'] or {}).get('t', '—')),
      ("прожила, тиков", (ch['lifespan'] or {}).get('ticks', '—')),
      ("действий", ch['n_acts']),
      ("смерть", f"день {dth['t']} ({dth['cause']})" if dth else "пережила прогон"),
  ])}</div>
  <div class="panel"><h2>Дом</h2>{_dl([
      ("корень дома", ho['house_root']),
      ("основатель", "да" if ho['is_founder'] else "нет"),
      ("поколение", ho['generation_depth']),
      ("детей", ho['n_children']),
      ("душ в доме", ho['house_size']),
  ])}</div>
  <div class="panel"><h2>Связи</h2>{_dl([
      ("знала", re_['n_known']),
      ("говорила", t['n_spoke']),
      ("слышала", t['n_heard']),
      ("клеймо", ", ".join(rep['branded_at_end']) if rep['ever_branded'] else "не носила"),
      ("тиков под клеймом", rep['ticks_branded']),
  ])}</div>
  <div class="panel"><h2>Земля</h2>{_dl([
      ("владений", pr['n_tenures']),
      ("тиков с землёй", pr['ticks_holding']),
      ("пик, клеток", pr['peak_cells']),
      ("в финале", len(pr['final_cells'])),
  ])}{_spark(pr['series'])}</div>
</div>
<div class="panel wide"><h2>Власть — потоки массы, роли раздельно</h2>
  <p class="note">Изъятие — это ПУЛ, делимый между вымогателями на клетке. Брутто события —
  не личное число: приписанная доля восстановлена по правилу дележа (поровну, остаток
  последнему) и сверена с реальными дельтами тел (гейт PF-SHARE). Где на клетке больше одной
  жертвы, подушевая потеря из журнала не выводима и в «приписано» НЕ входит.</p>
  {_dl([
      ("аппроприация — платила", f"{PR['appropriate']['payer']}× ({PT['rent_paid']} кг)"),
      ("аппроприация — получала", f"{PR['appropriate']['receiver']}× ({PT['rent_received']} кг)"),
      ("вымогательство — такер", f"{PR['extort']['taker']}× (заводилой {PR['extort']['taker_as_actor']}×)"),
      ("· брутто по этим событиям", f"{PT['extort_gross']} кг", "sub"),
      ("· приписано ей", f"{PT['extort_attributed']} кг", "sub emph"),
      ("· из них взяла одна", f"{PT['extort_solo']} кг", "sub"),
      ("вымогательство — жертва", f"{PR['extort']['victim']}× ({PT['extorted_from_attributed']} кг"
                                  + (f", ещё {PT['extorted_from_unresolved']} неразрешимых"
                                     if PT['extorted_from_unresolved'] else "") + ")"),
      ("ремитта — отдала / приняла", f"{PR['delegate_remit']['remitter']}× ({PT['remitted']} кг)"
                                     f" / {PR['delegate_remit']['root']}× ({PT['received_remit']} кг)"),
      ("платила и отнимала на той же клетке в тот же день",
       f"{PC['paid_and_took_same_tick_cell']}× из {PC['of_n_paid']}; "
       f"жертва оказывалась тем же рантье {PC['victim_was_the_landlord']}×"),
      ("получала дань и была обобрана там же в тот же день",
       f"{PC['received_and_was_robbed_same_tick_cell']}× из {PC['of_n_received']}; "
       f"грабители оказывались теми же арендаторами {PC['robbers_were_the_tenants']}×"),
      ("ИТОГО по властным потокам", f"{PT['net']:+} кг", "emph"),
  ])}</div>
<footer>Noether · E1 карточка пешки · сцена seed {scene['seed']}, {scene['days']} дней,
G2-ON + intent=reflex · карточка v{CARD_VERSION} · <code>sha {card['sha']}</code><br>
Проекции поверх единого EventLog; читатель мира не менял (E1-VOFF).</footer>
</div>"""
    return (f"<!doctype html><html lang=ru><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Пешка #{oid} — {html.escape(arc)}</title><style>{_CSS}</style></head>"
            f"<body>{body}</body></html>")
