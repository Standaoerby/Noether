# WO-30 — Noether viz PR #30 «β-battery + поток оборота»

> Наряд для Claude Code. Самодостаточный. Всё зовёт реальные имена из текущего `viz/`
> (сверено с `capture.py`/`schema.py` в main после PR #29). Канон не трогаем.

## Рамка

- **Ветка:** `feat/viz-battery` от свежего `main` (после мёржа PR #29).
- **Меняем файлы:** `viz/schema.py`, `viz/capture.py`, `viz/static/{index.html,viz.js,viz.css}`.
- **НЕ трогаем:** `Code/**`, `viz/server.py`.
- **Гардрейл (жёсткий, часть приёмки):** `git diff main -- Code/` обязан быть **пуст**.
  Снимок строго read-only; безопасность доказывается snapshot-safe гейтом на каждом мире.
- **Паттерн:** ты открываешь PR, мёрж делает Stan. origin/main руками не трогать.

## Контекст (что уже есть)

Визуализатор β стоит поверх снятого состояния сим-мира, read-only. Готово и влито:
PR #26 (`schema.py`+`capture.py`, 4-гейтный снимок), #27 (`server.py`, FastAPI над `runs/`),
#28 (двухпанельный canvas B0│B1), #29 (таймлайн-спарки + play + контраст-плашка + легенда).
`capture()` уже **generic по реестру `WORLDS`** — новый мир добавляется записью в dict,
логика гейта общая. Этот WO наполняет реестр всей property-аркой и добавляет поток оборота.

---

## Задача 1 — параметризовать B0-guard в `capture.py`

Сейчас B0-гейт хардкодит инвариант присвоения:
```python
ok_b0 = (fpb0 == spec["B0_anchor"] and wb0._appropriated_total == 0.0)
```
Новые миры имеют СВОЙ инвариант-нуля (`_levy_total==0` / `not _house` / `_traded==0`).
Ввести в спеку мира ключ `B0_guard` (callable мир→bool) и звать его:

```python
ok_b0 = (fpb0 == spec["B0_anchor"] and spec["B0_guard"](wb0))
```
В `print` строки B0-гейта убрать частное `appropriated_total=...` (или заменить на
обобщённое `guard_ok={spec["B0_guard"](wb0)}`). Больше в `capture()` менять нечего —
шаги 2 (reproducibility), 3 (capture-loop), 4 (snapshot-safe) уже generic.

---

## Задача 2 — три мира в реестр `WORLDS` (`capture.py`)

Импорты добавить рядом с существующим `from sim_appropriation import ...`:
```python
from sim_institution import run_institution, institution_fingerprint      # noqa: E402
from sim_inheritance import run_inheritance, inheritance_fingerprint      # noqa: E402
from sim_trade       import run_trade,       trade_fingerprint            # noqa: E402
```

Добавить в существующую запись `appropriation` ключ `B0_guard` (чтобы generic-гейт
работал единообразно):
```python
"B0_guard": lambda w: w._appropriated_total == 0.0,
```

Три новые записи (конфиги/якоря — из форензики Code/, дословно):

```python
"institution": {
    "run": run_institution, "fp": institution_fingerprint,
    "B0": dict(sigma=0.0, enforce=False, appropriation=0.0, owner_policy="founders",
               arena_side=None),
    "B0_anchor": CANON_COMM,                       # "a91480561b6de937"
    "B0_guard": lambda w: w._levy_total == 0.0,
    "headline": dict(sigma=0.5, enforce=True, owner_policy="claim", arena_side=6),
    "baseline": dict(sigma=0.0, enforce=False, appropriation=0.5,
                     owner_policy="claim", arena_side=6),   # присвоение ON, институт OFF
},
"inheritance": {
    "run": run_inheritance, "fp": inheritance_fingerprint,
    "B0": dict(heritable=False, sigma=0.0, enforce=False, appropriation=0.0,
               owner_policy="founders", arena_side=None),
    "B0_anchor": CANON_COMM,
    "B0_guard": lambda w: not w._house,
    "headline": dict(heritable=True, appropriation=0.5, owner_policy="claim", arena_side=6),
    "baseline": dict(heritable=False, appropriation=0.5, owner_policy="claim", arena_side=6),
},
"trade": {
    "run": run_trade, "fp": trade_fingerprint,
    "B0": dict(trade=False, appropriation=0.0, owner_policy="founders", arena_side=None),
    "B0_anchor": CANON_COMM,
    "B0_guard": lambda w: w._traded == 0,
    "headline": dict(trade=True, trade_mode="market", price_frac=0.25,
                     appropriation=0.5, owner_policy="claim", arena_side=6),
    "baseline": dict(trade=False, appropriation=0.5, owner_policy="claim", arena_side=6),
},
```

**Сверить перед прогоном** (сигнатуры `run_*`, НЕ гадать — открыть файлы):
- `run_institution(sigma=0.0, enforce=False, enforcers=M_E, owner_policy=..., appropriation=..., arena_side=..., days=...)`
- `run_inheritance(heritable=False, heir_fallback="revert", sigma=0.0, enforce=False, appropriation=..., owner_policy=..., arena_side=..., days=...)`
- `run_trade(trade=False, trade_mode="market", price_frac=PRICE_FRAC, appropriation=..., owner_policy=..., arena_side=..., days=...)`

Критично: `capture()` шаг 3 зовёт `run(**cfg, days=0)` для построения нетронутого мира.
Все три `run_*` ДОЛЖНЫ принимать `days` kwarg (как `run_appropriation`). Если какой-то не
принимает — не подгонять костылём, а ОСТАНОВИТЬСЯ и сообщить в отчёте (это сигнал, что
конструкция мира иная; решим вместе).

---

## Задача 3 — поток оборота в `SnapFrame` (`schema.py`)

Добавить в dataclass `SnapFrame` два поля (births/deaths за тик — делает насос видимым):
```python
births: list   # [[oid, i, j], ...] — агенты, появившиеся с прошлого СНЯТОГО кадра
deaths: list   # [[i, j], ...]      — позиции, где агент исчез с прошлого снятого кадра
```

Считать **дельтой по кадрам** (НЕ читать event-log — чтобы schema не тянула структуру лога):
- `frame_from_world(w, t, prev=None)` — `prev` = предыдущий снятый SnapFrame (или None).
- `births` = агенты текущего кадра, чьих oid не было в `prev.agents`.
- `deaths` = позиции `[i,j]` из `prev.agents`, чьих oid нет в текущем кадре.
- `prev is None` (первый кадр) → оба списка пустые.

В `capture.py` capture-loop передавать предыдущий кадр:
```python
frames = []
prev = None
for _ in range(DAYS):
    ws.step()
    if ws.t % every == 0 or ws.t == DAYS:
        fr = frame_from_world(ws, ws.t, prev)
        frames.append(fr); prev = fr
```
(при `every>1` дельта считается между снятыми кадрами — это ок, поток на разреженной сетке.)

`frames_to_jsonl` / `frames_from_jsonl` менять НЕ нужно — `asdict` / `SnapFrame(**...)`
подхватят новые поля автоматически (dataclass).

**fp-нейтральность:** новые поля живут в снимке, не в мире. `*_fingerprint(w)` мир не читает
из снимка → snapshot-safe гейт остаётся зелёным. Гейт это и докажет.

---

## Задача 4 — прогнать батарею (локально, приложить вывод в отчёт)

```
python capture.py appropriation headline ; python capture.py appropriation baseline
python capture.py institution  headline ; python capture.py institution  baseline
python capture.py inheritance  headline ; python capture.py inheritance  baseline
python capture.py trade        headline ; python capture.py trade        baseline
```
8 прогонов. Каждый печатает B0 / reproducibility / snapshot-safe + финальные метрики.
**В отчёт вставить все fp-строки** — Stan/Гайка сверят с vault-глоссой.

---

## Задача 5 — галерея на фронте (`viz/static/`)

`index.html` — селектор мира над `#panels`:
```html
<select id="world">
  <option value="appropriation">присвоение (23)</option>
  <option value="institution">институт (24)</option>
  <option value="inheritance">наследование (25)</option>
  <option value="trade">рынок (27)</option>
</select>
```
плюс тумблер потока в `#toggles`:
```html
<label><input type="checkbox" id="ly-flow" /> оборот</label>
```

`viz.js`:
- `RUNS` больше не константа, а функция выбранного мира:
  `const runsFor = (w) => ({ baseline: `${w}_baseline`, headline: `${w}_headline` });`
- при смене `#world`: перезагрузить обе пары (`loadRun`), пересчитать `computeScales()` +
  `computeSeries()`, `draw(state.tMin)`. Спарки/плашка/play из PR #29 переиспользуются как есть.
- слой `flow` в `state.layers` (default false); в `renderFrame`, после слоя тел, если включён:
  - `frame.births` → зелёная вспышка в `(j,i)` (яркая точка, r ~ полклетки);
  - `frame.deaths` → красная вспышка в `(j,i)`.
  Насос виден: у сытых владельцев частые зелёные, у базы — красные.

Заголовки панелей — двухрегистровые из PR #29 («Мир без собственности» / «Мир с собственностью»),
но текст мира берётся из выбора селектора (можно добавить мелкую строку с именем мира).

---

## Гейт приёмки PR #30

```
capture-generic : B0_guard параметризован; 4-гейт работает для всех миров
battery         : 8 прогонов (4 мира × head/base); B0 == a91480561b6de937 и guard==0 везде
fp-сверка       : headline-метрики каждого мира — приложены в отчёт для сверки с vault:
                   institution — box коллапс (мало живых, 0 клеток) / open стражи ~14× per-capita
                   inheritance — домов меньше (−6/−39 диапазон), доля топ-дома плоская
                   trade       — доля владельцев 0.34→0.48, база прорежена (alive ниже)
flow            : births/deaths в кадре; snapshot-safe ЗЕЛЁНЫЙ (поток fp не сломал)
gallery         : селектор мира рисует любую пару; спарки/плашка/play работают на каждой
flow-render     : тумблер «оборот» — зелёные вспышки рождений, красные смертей
no-canon        : git diff main -- Code/ пуст; server.py не тронут; ноль console-ошибок
```

## Что вернуть в отчёте

1. Ссылка на PR + `git diff --stat main` (должно быть только `viz/schema.py`,
   `viz/capture.py`, `viz/static/*`).
2. Полный вывод 8 прогонов (fp-строки B0/reproducibility/snapshot-safe + финальные метрики).
3. Подтверждение `git diff main -- Code/` == пусто.
4. Скрин/подтверждение галереи: переключение мира рисует пару, тумблер «оборот» даёт вспышки.
5. Любые отклонения (особенно если `run_*` не принял `days=0`).
