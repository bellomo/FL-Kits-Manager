"""Stripes, panels and blocks of a shirt from its photo -> "rects" for team.json (painted by texture.py).

How: the torso of the photo (sleeves excluded) is cut into a grid of small cells; each cell takes the fabric colour
most of its pixels are nearest to (shadows and folds merged into the colour they darken). The most common colour is
the body; areas of another colour that are bands (tall, or nearly as wide as the torso, or tall-ish along a side)
become rectangles. Compact areas are logos (sponsor, crest): their cells take the colour above or below, so a sponsor
crossing a stripe does not cut it.

Mapping to the texture: x as spec.py (torso = TORSO_PX around 1024; bands touching the torso side go on to the edge of
the body column, round the flanks); y as spec.py in the logo zone, then stretched so that the hem lands on the bottom
of the front (y 1870) or the top of the back (y 0). The front comes from the shirt photo, the back from the back photo
(upside down: x mirrored); without a back photo the front bands are mirrored onto the back.

Limits: sleeve stripes, diagonal bands, gradients and tonal patterns (close colours) are not read.
"""

import colorsys
from collections import Counter

import numpy as np
from PIL import Image

from flkm.photokit.colour import apply_gain, colour_distance, is_shade, rgb_to_hex, tone_gain
from flkm.photokit.logo import analyse_garment
from flkm.photokit.photo import label_regions
from flkm.photokit.spec import TORSO_PX, Y0, YK

BODY_X = (650, 1330)  # body column of the texture
FRONT_Y = (1012, 1870)  # front: collar seam .. hem
BACK_Y = (0, 1012)  # back (upside down): hem .. collar seam
TOP_CY = 0.12  # above this the photo shows the collar and the neck opening
COLS = 80  # grid cells across the torso
EDGE_PANEL = 20  # texture pixels: a band at the torso side at least this wide is a side panel, a thinner one a piping
VIS_PAD = 26  # texture pixels outside the measured torso (764-1284) still seen from the front (738-1310)


# --- photo fractions -> texture -----------------------------------------------------------------------------------
def texture_x(f: float, back: bool = False) -> int:
    x = 1024 + (f - 0.5) * TORSO_PX
    return round(2048 - x if back else x)


def front_texture_y(cy: float, hem: float) -> int:
    y = Y0 + YK * cy if cy <= 0.6 else (Y0 + YK * 0.6) + (cy - 0.6) * (FRONT_Y[1] - Y0 - YK * 0.6) / (hem - 0.6)
    return int(round(min(max(y, FRONT_Y[0]), FRONT_Y[1])))


def back_texture_y(cy: float, hem: float) -> int:
    top = 1155  # mirror of the front: 1012 + (1040 - Y0)
    y = top - YK * cy if cy <= 0.6 else (top - YK * 0.6) * (1 - (cy - 0.6) / (hem - 0.6))
    return int(round(min(max(y, BACK_Y[0]), BACK_Y[1])))


def _front_cy(y: float, hem: float) -> float:
    """Inverse of front_texture_y."""
    mid = Y0 + YK * 0.6
    return (y - Y0) / YK if y <= mid else 0.6 + (y - mid) * (hem - 0.6) / (FRONT_Y[1] - mid)


def mirror_rects_to_back(rects: list[dict], hem: float = 0.98) -> list[dict]:
    """Front body rects -> the same bands on the back (no back photo). Side panels and pipings of one side only are
    left out: the back is not seen, they are not invented there."""
    out = []
    for r in rects:
        if r.get("region", "body") != "body" or r["y"][0] < FRONT_Y[0]:
            continue
        if (r["x"][0] <= BODY_X[0]) != (r["x"][1] >= BODY_X[1]):
            continue
        y0 = BACK_Y[0] if r["y"][1] >= FRONT_Y[1] else back_texture_y(_front_cy(r["y"][1], hem), hem)
        y1 = BACK_Y[1] if r["y"][0] <= FRONT_Y[0] else back_texture_y(_front_cy(r["y"][0], hem), hem)
        # mirrored about the torso centre (1024); a band reaching both body edges reaches them on the back too
        x0 = BODY_X[0] if r["x"][1] >= BODY_X[1] else max(2048 - r["x"][1], BODY_X[0])
        x1 = BODY_X[1] if r["x"][0] <= BODY_X[0] else min(2048 - r["x"][0], BODY_X[1])
        if x1 > x0:
            out.append({"region": "body", "x": [x0, x1], "y": [y0, y1], "color": r["color"]})
    return out


# --- grid -> rectangles ---------------------------------------------------------------------------------------------
def _areas(grid: np.ndarray, body: int) -> list[tuple]:
    """4-connected areas of each non-body colour: [(colour, mask, c0, r0, c1, r1)]."""
    out = []
    for col in sorted(set(grid.ravel().tolist()) - {body}):
        lab, n = label_regions(grid == col)
        for i in range(1, n + 1):
            m = lab == i
            ys, xs = np.nonzero(m)
            out.append((col, m, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return out


def _is_band(m: np.ndarray, c0: int, r0: int, c1: int, r1: int) -> bool:
    """A band: tall, or nearly as wide as the torso, or tall-ish along a side; and filling its box (a diagonal stroke
    or scattered shading does not)."""
    rows, cols = m.shape
    h, w = (r1 - r0) / rows, (c1 - c0) / cols
    side = c0 == 0 or c1 == cols
    big = h >= 0.25 or w >= 0.85 or (side and h >= 0.15)
    return big and m[r0:r1, c0:c1].mean() >= 0.5


def find_band_rects(grid: np.ndarray, body: int) -> list[tuple]:
    """One straight rectangle per band of the grid: [(colour, c0, r0, c1, r1)]. A vertical band keeps the columns it
    fills in most rows (edges wobbling by a cell do not widen it), a horizontal one the rows."""
    out = []
    rows, cols = grid.shape
    for col, m, c0, r0, c1, r1 in _areas(grid, body):
        if not _is_band(m, c0, r0, c1, r1):
            continue
        sub = m[r0:r1, c0:c1]
        if (r1 - r0) / rows >= (c1 - c0) / cols:
            cnt = sub.sum(0)
            keep = np.nonzero(cnt >= 0.6 * cnt.max())[0]
            out.append((int(col), c0 + keep.min(), r0, c0 + keep.max() + 1, r1))
        else:
            cnt = sub.sum(1)
            keep = np.nonzero(cnt >= 0.6 * cnt.max())[0]
            out.append((int(col), c0, r0 + keep.min(), c1, r0 + keep.max() + 1))
    return out


def _same_fabric(c, p) -> bool:
    """Two palette colours of one fabric: close, one a shadow of the other (either way), or two light greys or whites
    differing only by the light (a white shirt brighter at the top)."""
    if sum(abs(a - b) for a, b in zip(c, p)) < 80:
        return True
    if is_shade(rgb_to_hex(c), rgb_to_hex(p)) or is_shade(rgb_to_hex(p), rgb_to_hex(c)):
        return True
    hc, sc, vc = colorsys.rgb_to_hsv(*[v / 255 for v in c])
    hp, sp, vp = colorsys.rgb_to_hsv(*[v / 255 for v in p])
    if sc < 0.12 and sp < 0.12 and abs(vc - vp) < 0.22:
        return True
    # same hue and saturation, a bit lighter or darker (highlight on a yellow shirt); navy and sky blue stay apart
    dh = min(abs(hc - hp), 1 - abs(hc - hp))
    return sc >= 0.3 and sp >= 0.3 and dh < 0.05 and abs(sc - sp) < 0.25 and abs(vc - vp) < 0.25


def _palette(px: np.ndarray, fabric) -> list[tuple]:
    """Fabric colours: colours of the torso pixels plus the photo's fabric colours, shadows merged."""
    q = Image.fromarray(px[None, :, :]).quantize(10, method=Image.Quantize.MEDIANCUT)
    cols = np.array(q.getpalette()[:30]).reshape(-1, 3)
    counts = np.bincount(np.array(q).ravel(), minlength=10)[: len(cols)]
    cand = sorted(((counts[i], tuple(int(v) for v in cols[i])) for i in range(len(cols)) if counts[i]), reverse=True)
    cand = [c for n, c in cand if n >= 0.01 * len(px)] + [tuple(p) for p in fabric]
    pal = []
    for c in cand:
        if not any(_same_fabric(c, p) for p in pal):
            pal.append(c)
    return pal


def _fill_vertical(g: np.ndarray, unknown: np.ndarray) -> np.ndarray:
    """Unknown cells take the colour of the nearest known cell in the same column (above or below)."""
    g = g.copy()
    rows, cols = g.shape
    for c in range(cols):
        known = [r for r in range(rows) if not unknown[r, c]]
        if not known:
            continue
        for r in range(rows):
            if unknown[r, c]:
                g[r, c] = g[min(known, key=lambda k: (abs(k - r), k)), c]
    return g


def pair_side_rects(sides: list[dict], shade: dict) -> list[dict]:
    """Side panels and pipings at the body edges. A left one and a right one of the same colour get the same width
    and length (averaged): kits are symmetric, photos are not (perspective, folds). A panel shows on the front as wide
    as on the photo (its inner edge moved out by the flank seen beyond the torso) and goes on round the flank to the
    body edge; a piping keeps its width at the body edge."""
    out, used = [], set()
    for i, s in enumerate(sides):
        if i in used:
            continue
        mates = [
            j
            for j, t in enumerate(sides)
            if j not in used and j != i and t["col"] == s["col"] and t["left"] != s["left"]
        ]
        group = [s] + ([sides[mates[0]]] if mates else [])
        used.update([i] + mates[:1])
        w = round(sum(g["w"] for g in group) / len(group))
        y = [round(sum(g["y"][k] for g in group) / len(group)) for k in (0, 1)]
        for left in sorted({g["left"] for g in group}):
            if w >= EDGE_PANEL:  # panel: front width as on the photo, the flank behind covered too
                x = [BODY_X[0], texture_x(0) - VIS_PAD + w] if left else [texture_x(1) + VIS_PAD - w, BODY_X[1]]
            else:  # piping on the side seam
                x = [BODY_X[0], BODY_X[0] + w] if left else [BODY_X[1] - w, BODY_X[1]]
            out.append({"region": "body", "x": x, "y": y, "color": shade[s["col"]]})
    return out


def read_pattern(im: Image.Image, side: str = "front", debug: bool = False, skip: list | None = None) -> dict:
    """{'body': '#rrggbb', 'rects': [{'region': 'body', 'x', 'y', 'color'}], 'hem': cy} of one shirt photo; debug adds
    the grid and palette; skip: boxes of the photo (pixels x0, y0, x1, y1) that are not the kit (the player's number
    and name on a back photo): they take the colour above or below them."""
    ctx = analyse_garment(im, "big")
    a, g = ctx["a"], ctx["g"]
    gy0, gy1 = ctx["Y0"], ctx["Y1"]
    t0, t1 = ctx["T0"], ctx["T1"]
    h = gy1 - gy0
    rows_g = np.nonzero(g[:, (t0 + t1) // 2])[0]
    hem_row = rows_g.max() + 1 if len(rows_g) else gy1
    hem = (hem_row - gy0) / h
    top = gy0 + int(TOP_CY * h)
    torso = g[top:hem_row, t0:t1]
    px = a[top:hem_row, t0:t1][torso]
    pal = _palette(px, ctx["fabric"])
    cls = np.argmin([np.abs(a[top:hem_row, t0:t1].astype(int) - np.array(p)).sum(2) for p in pal], axis=0)
    cell = (t1 - t0) / COLS
    rows = max(1, int(round((hem_row - top) / cell)))
    grid = np.zeros((rows, COLS), int)
    unknown = np.zeros((rows, COLS), bool)
    for r in range(rows):
        ys = slice(int(r * cell), max(int((r + 1) * cell), int(r * cell) + 1))
        for c in range(COLS):
            xs = slice(int(c * cell), max(int((c + 1) * cell), int(c * cell) + 1))
            m = torso[ys, xs]
            if m.sum() < 0.5 * m.size:
                unknown[r, c] = True
                continue
            grid[r, c] = np.bincount(cls[ys, xs][m], minlength=len(pal)).argmax()
    s = ctx["scale"]
    for bx0, by0, bx1, by1 in skip or []:
        c0, c1 = max(0, int((bx0 * s - t0) // cell)), min(COLS, int(np.ceil((bx1 * s - t0) / cell)))
        r0, r1 = max(0, int((by0 * s - top) // cell)), min(rows, int(np.ceil((by1 * s - top) / cell)))
        unknown[r0:r1, c0:c1] = True
    grid = _fill_vertical(grid, unknown)
    body = Counter(grid.ravel().tolist()).most_common(1)[0][0]
    # compact areas of another colour are logos: their cells take the colour above or below
    logo = np.zeros_like(unknown)
    band = np.zeros_like(unknown)
    areas = _areas(grid, body)
    for col, m, c0, r0, c1, r1 in areas:
        if _is_band(m, c0, r0, c1, r1):
            band |= m
        else:
            logo[r0:r1, c0:c1] = True  # whole box: a logo's cells of the body colour are not fabric either
    logo &= ~band  # ...but bands crossing the box stay
    grid = _fill_vertical(grid, logo | unknown)
    # colour of each class = median of its pixels on the torso (the true shade, not the palette entry)
    shade = {}
    for i in set(grid.ravel().tolist()):
        sel = px[cls[torso] == i]
        shade[i] = rgb_to_hex(np.median(sel, 0)) if len(sel) else rgb_to_hex(pal[i])
    rects, sides = [], []
    for col, c0, r0, c1, r1 in find_band_rects(grid, body):
        if c1 - c0 < 2:
            continue
        f0, f1 = c0 / COLS, c1 / COLS
        # thin piping on the side seam: kept only when it runs the whole height (partial ones come out wrong)
        if (c0 == 0 or c1 == COLS) and (f1 - f0) * TORSO_PX < EDGE_PANEL and (r1 - r0) < 0.9 * rows:
            continue
        cy0, cy1 = TOP_CY + r0 * cell / h, TOP_CY + r1 * cell / h
        if side == "back":
            x0, x1 = texture_x(f1, True), texture_x(f0, True)
            left, right = c1 == COLS, c0 == 0
            y0 = BACK_Y[0] if r1 == rows else back_texture_y(cy1, hem)
            y1 = BACK_Y[1] if r0 == 0 else back_texture_y(cy0, hem)
        else:
            x0, x1 = texture_x(f0), texture_x(f1)
            left, right = c0 == 0, c1 == COLS
            y0 = FRONT_Y[0] if r0 == 0 else front_texture_y(cy0, hem)
            y1 = FRONT_Y[1] if r1 == rows else front_texture_y(cy1, hem)
        if left != right:  # side panel or piping: placed after pairing left with right
            sides.append({"left": left, "w": x1 - x0, "y": [y0, y1], "col": col})
            continue
        if left:  # band across the whole torso
            x0, x1 = BODY_X
        rects.append({"region": "body", "x": [x0, x1], "y": [y0, y1], "color": shade[col]})
    rects += pair_side_rects(sides, shade)
    res = {"body": shade[body], "rects": rects, "hem": round(hem, 4)}
    if debug:
        res.update(_grid=grid, _pal=pal, _shade=shade, _body=body)
    return res


def paint_row(res: dict, y: int, x0: int = BODY_X[0], x1: int = BODY_X[1]) -> list[str]:
    """Colour of each texture x on row y (body + rects, later rects on top), as texture.py paints them."""
    row = [res["body"]] * (x1 - x0)
    for r in res["rects"]:
        if r.get("region", "body") == "body" and r["y"][0] <= y < r["y"][1]:
            for x in range(max(x0, r["x"][0]), min(x1, r["x"][1])):
                row[x - x0] = r["color"]
    return row


TONES = ("auto", "front", "back")  # which photo gives the colours of a kit with a front and a back photo


def _toned(rects: list[dict], gain) -> list[dict]:
    return [dict(r, color=apply_gain(r["color"], gain)) for r in rects]


def read_kit_pattern(front: str, back: str | None = None, tone: str = "auto", skip: list | None = None) -> dict:
    """Body colour + rects for the front and the back of one kit (paths of the shirt photo and the back photo), and
    the gain that puts the front photo's other colours (sleeves, collar) in the kit's tone.
    tone (with a back photo): "auto" = a back of another colour is a real one (Catania home: blue back); "front" or
    "back" = the two photos show the same kit in two tones (photos from two sites): that photo's tone for both.
    skip: boxes of the back photo left out (the player's number and name, see read_pattern)."""
    fr = read_pattern(Image.open(front))
    none = (1.0, 1.0, 1.0)
    if not back:
        return {"body": fr["body"], "rects": fr["rects"] + mirror_rects_to_back(fr["rects"], fr["hem"]), "gain": none}
    bk = read_pattern(Image.open(back), side="back", skip=skip)
    if tone == "front":
        rects = fr["rects"] + _toned(bk["rects"], tone_gain(bk["body"], fr["body"]))
        return {"body": fr["body"], "rects": rects, "gain": none}
    if tone == "back":
        gain = tone_gain(fr["body"], bk["body"])
        return {"body": bk["body"], "rects": _toned(fr["rects"], gain) + bk["rects"], "gain": gain}
    rects = list(fr["rects"])
    if colour_distance(bk["body"], fr["body"]) >= 60:
        rects.append({"region": "body", "x": list(BODY_X), "y": list(BACK_Y), "color": bk["body"]})
    return {"body": fr["body"], "rects": rects + bk["rects"], "gain": none}
