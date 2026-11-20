#!/usr/bin/env python3
"""Bouwt software/demo/metromap-live.html uit de KiCad-print.

Leest hardware/metromap.kicad_pcb, haalt de LED-posities (in de volgorde van de
dataketen), de koperen kaart, de silkscreen-lijnen en -teksten eruit en zet die
als JSON in src/template.html.

    python3 software/demo/tools/build.py

Draai dit opnieuw na elke wijziging aan de print.
"""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PCB = ROOT / "hardware" / "metromap.kicad_pcb"
DEMO = Path(__file__).resolve().parents[1]
TEMPLATE = DEMO / "src" / "template.html"
OUT = DEMO / "metromap-live.html"

ART_REF = "G***"            # footprint met de koperen kaart (water)
DATA_IN_NET = "/LEDs/DATA_IN"

# ---------------------------------------------------------------- s-expressions
_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text):
    stack = [[]]
    for m in _TOK.finditer(text):
        t = m.group()
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop()
            stack[-1].append(node)
        elif t[0] == '"':
            stack[-1].append(t[1:-1].replace('\\"', '"'))
        else:
            stack[-1].append(t)
    return stack[0][0]


def find(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def get(node, name):
    r = find(node, name)
    return r[0] if r else None


def props(node):
    return {p[1]: p[2] for p in find(node, "property")}


# ---------------------------------------------------------------- geometry
def fp_xf(fp, x, y):
    at = get(fp, "at")
    x0, y0 = float(at[1]), float(at[2])
    a = math.radians(float(at[3]) if len(at) > 3 else 0)
    return x0 + x * math.cos(a) + y * math.sin(a), y0 - x * math.sin(a) + y * math.cos(a)


def circle(ax, ay, bx, by, cx, cy):
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax*ax + ay*ay) * (by - cy) + (bx*bx + by*by) * (cy - ay) + (cx*cx + cy*cy) * (ay - by)) / d
    uy = ((ax*ax + ay*ay) * (cx - bx) + (bx*bx + by*by) * (ax - cx) + (cx*cx + cy*cy) * (bx - ax)) / d
    return math.hypot(ax - ux, ay - uy)


def main():
    t = parse(PCB.read_text(encoding="utf-8"))

    # board origin = top-left of Edge.Cuts
    xs, ys = [], []
    for g in t:
        if isinstance(g, list) and g[0] in ("gr_line", "gr_arc") and get(g, "layer")[1] == "Edge.Cuts":
            for k in ("start", "end"):
                e = get(g, k)
                xs.append(float(e[1]))
                ys.append(float(e[2]))
    X0, Y0 = min(xs), min(ys)
    r2 = lambda v: round(v, 2)
    P = lambda x, y: "%g,%g" % (r2(x - X0), r2(y - Y0))

    water, leds, holes, pads = [], {}, [], []
    for fp in find(t, "footprint"):
        p = props(fp)
        ref = p.get("Reference", "")
        if ref == ART_REF:
            for g in find(fp, "fp_poly"):
                pts, last = [], None
                for a in find(get(g, "pts"), "xy"):
                    q = fp_xf(fp, float(a[1]), float(a[2]))
                    if last and math.hypot(q[0] - last[0], q[1] - last[1]) < 0.06:
                        continue
                    pts.append(q)
                    last = q
                water.append("M" + " ".join(P(*q) for q in pts) + "Z")
        elif p.get("Value", "").startswith("SK6812"):
            at = get(fp, "at")
            pads_ = {pd[1]: get(pd, "net")[-1] for pd in find(fp, "pad") if get(pd, "net")}
            leds[ref] = dict(x=float(at[1]), y=float(at[2]), din=pads_.get("4"), dout=pads_.get("2"))
        elif ref.startswith("H") and p.get("Value", "").startswith("Mounting"):
            at = get(fp, "at")
            holes.append([r2(float(at[1]) - X0), r2(float(at[2]) - Y0)])
        elif "TOUCH" in p.get("Value", "").upper() or ref in ("TP5", "TP6"):
            at = get(fp, "at")
            pads.append([r2(float(at[1]) - X0), r2(float(at[2]) - Y0)])

    # follow the data chain DIN -> DOUT
    by_din = {v["din"]: k for k, v in leds.items()}
    cur = by_din[DATA_IN_NET]
    order = [cur]
    while leds[cur]["dout"] in by_din:
        cur = by_din[leds[cur]["dout"]]
        order.append(cur)
    assert len(order) == len(leds), f"keten heeft {len(order)} van {len(leds)} LEDs"

    tracks = []
    for g in t:
        if not (isinstance(g, list) and g[0] in ("gr_line", "gr_arc") and get(g, "layer")[1] == "F.SilkS"):
            continue
        s = [float(v) for v in get(g, "start")[1:3]]
        e = [float(v) for v in get(g, "end")[1:3]]
        if g[0] == "gr_line":
            d = f"M{P(*s)} L{P(*e)}"
        else:
            m = [float(v) for v in get(g, "mid")[1:3]]
            r = circle(*s, *m, *e)
            cross = (m[0] - s[0]) * (e[1] - s[1]) - (m[1] - s[1]) * (e[0] - s[0])
            d = f"M{P(*s)} A{r2(r)},{r2(r)} 0 0 {1 if cross > 0 else 0} {P(*e)}"
        tracks.append([d, float(get(get(g, "stroke"), "width")[1])])

    labels = []
    for g in find(t, "gr_text"):
        layer = get(g, "layer")[1]
        if layer not in ("F.SilkS", "F.Cu"):
            continue
        at = get(g, "at")
        eff = get(g, "effects")
        j = get(eff, "justify")
        size = float(get(get(eff, "font"), "size")[1])
        labels.append(dict(t=g[1].replace("\\n", "\n"), x=r2(float(at[1]) - X0), y=r2(float(at[2]) - Y0),
                           j=j[1:] if j else [], s=size, cu=layer == "F.Cu"))

    board = dict(water=water, tracks=tracks, labels=labels, holes=holes, pads=pads,
                 leds=[[r2(leds[r]["x"] - X0), r2(leds[r]["y"] - Y0)] for r in order],
                 refs=order)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*BOARD_JSON*/", json.dumps(board, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(order)} LEDs, {len(water)} kaartvlakken, {len(labels)} teksten")


if __name__ == "__main__":
    main()
