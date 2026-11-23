"""Logos on a flat shirt photo (sponsor, maker, crest): found and cut out with their own colours.

cut_logos writes <photo>_cNN.png (RGBA, background removed) for every candidate and _candidates_<photo>.json with the
position and size of each (cx, cy, w, h of the garment; tx, tw of the torso) and its role from where it sits on the
torso (front: maker / crest / sponsor / other; back photos: sponsor / other). join_candidates makes one logo of
candidates split in two (_jNN-NN.png): only the parts lying mostly inside the joined boxes are kept, so lines of the
shirt's graphic crossing the logo in the same colour are dropped. Limit: tonal logos (the colour of the fabric) are not
found.
"""

import json
import os

import numpy as np
from PIL import Image, ImageFilter

from flkm.photokit import PhotoKitError
from flkm.photokit.colour import dominant_colours, hex_to_rgb
from flkm.photokit.photo import filled_garment_mask, garment_mask, label_regions, photo_side, rgb_array

WORK = 800  # analysis size (long side)


def find_fabric_colours(im, min_share: float = 0.03, min_spread: float = 0.3, grid: int = 6) -> list[tuple]:
    """Colours of the fabric: dominant colours spread over the garment (present in at least min_spread of the grid
    cells). A big sponsor is a lot of pixels, but all in the chest cells."""
    a = rgb_array(im) if isinstance(im, Image.Image) else im
    small = Image.fromarray(a)
    small.thumbnail((400, 400))  # the size dominant_colours works at
    s = np.array(small)
    g = filled_garment_mask(s)
    d = dominant_colours(small, k=12, mask=garment_mask(s), merge=25)
    cand = [hex_to_rgb(c) for c, f in d if f >= min_share] or [hex_to_rgb(d[0][0])]
    cls = np.argmin([np.abs(s.astype(int) - np.array(p)).sum(2) for p in cand], axis=0)
    ys, xs = np.nonzero(g)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    spread = []
    for i in range(len(cand)):
        hit = n = 0
        for cy in range(grid):
            for cx in range(grid):
                sl = (
                    slice(y0 + (y1 - y0) * cy // grid, y0 + (y1 - y0) * (cy + 1) // grid),
                    slice(x0 + (x1 - x0) * cx // grid, x0 + (x1 - x0) * (cx + 1) // grid),
                )
                gm = g[sl]
                if gm.sum() < 20:
                    continue
                n += 1
                hit += ((cls[sl] == i) & gm).sum() > 0.02 * gm.sum()
        spread.append(hit / max(n, 1))
    pal = [c for c, sp in zip(cand, spread) if sp >= min_spread]
    return pal or [cand[0]]


def _distance_to(a: np.ndarray, pal) -> np.ndarray:
    return np.min([np.abs(a.astype(int) - np.array(p)).sum(2) for p in pal], axis=0)


def _distance_to_blends(a: np.ndarray, pal) -> np.ndarray:
    """Distance of each pixel to the nearest mix of two fabric colours (segment between them, L1)."""
    x = a.astype(float)
    best = np.full(a.shape[:2], 1e9)
    for i in range(len(pal)):
        for j in range(i + 1, len(pal)):
            p, q = np.array(pal[i], float), np.array(pal[j], float)
            v = q - p
            t = np.clip(((x - p) * v).sum(2) / max((v * v).sum(), 1), 0, 1)[..., None]
            best = np.minimum(best, np.abs(x - (p + t * v)).sum(2))
    return best


def _components(mask: np.ndarray, join: int) -> list[np.ndarray]:
    """Pixel masks of the groups of mask pixels that touch after a dilation (letters -> one word); join = 0: pixel
    connected parts only."""
    grown = Image.fromarray(mask.astype(np.uint8) * 255)
    for _ in range(max(1, join // 4) if join else 0):
        grown = grown.filter(ImageFilter.MaxFilter(7))
    lab, n = label_regions(np.array(grown) > 0)
    return [m for m in ((lab == i) & mask for i in range(1, n + 1)) if m.any()]


def _width(mask: np.ndarray) -> int:
    xs = np.nonzero(mask.any(0))[0]
    return xs[-1] - xs[0] + 1 if len(xs) else 0


def find_torso_edges(g: np.ndarray, x0: int, x1: int, y0: int, y1: int) -> tuple[int, int]:
    """Left and right edge of the torso: the garment run through the centre on a row below the sleeves."""
    row = g[y0 + int(0.8 * (y1 - y0)), x0:x1]
    c = (x1 - x0) // 2
    if not row[c]:
        return x0, x1
    left = c
    while left > 0 and row[left - 1]:
        left -= 1
    right = c
    while right < len(row) - 1 and row[right + 1]:
        right += 1
    return x0 + left, x0 + right + 1


def _iou(a, b) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0


def _area(b) -> int:
    return (b[2] - b[0]) * (b[3] - b[1])


def share_inside(small, big) -> float:
    """Share of box small (x0, y0, x1, y1) that lies inside box big."""
    ix = max(0, min(small[2], big[2]) - max(small[0], big[0]))
    iy = max(0, min(small[3], big[3]) - max(small[1], big[1]))
    area = _area(small)
    return ix * iy / area if area else 0


def _merge(out: list, c: dict) -> None:
    """Adds candidate c unless it overlaps one already kept. The same logo found twice (colour split, two passes):
    the slightly bigger box holding the other wins (Catania 'Conveniente': the copy with the first letter)."""
    for i, o in enumerate(out):
        if _iou(c["box"], o["box"]) >= 0.4:
            if share_inside(o["box"], c["box"]) >= 0.95 and _area(c["box"]) <= 1.3 * _area(o["box"]):
                out[i] = c
            return
    out.append(c)


def _stacked(boxes) -> bool:
    """True if some of the boxes lie one above the other without sharing rows (two logos stacked)."""
    return any(a[3] <= b[1] or b[3] <= a[1] for i, a in enumerate(boxes) for b in boxes[i + 1 :])


def _drop_unions_and_fragments(cands: list[dict], share: float = 0.7) -> list[dict]:
    """A box holding other candidates stacked one above the other is a union of logos (sponsor above second sponsor):
    dropped. Boxes inside any other kept candidate are fragments of it (pieces of one word side by side): dropped."""
    boxes = [c["box"] for c in cands]
    held = [[j for j, b in enumerate(boxes) if j != i and share_inside(b, a) >= share] for i, a in enumerate(boxes)]
    union = {i for i, h in enumerate(held) if len(h) >= 2 and _stacked([boxes[j] for j in h])}
    frag = {j for i, h in enumerate(held) if i not in union for j in h}
    return [c for i, c in enumerate(cands) if i not in union and i not in frag]


def analyse_garment(im: Image.Image, mode: str = "spread", thr: int = 90) -> dict:
    """Analysis at WORK size: logo mask (pixels far from the fabric colours) and garment geometry. mode 'spread':
    fabric = colours spread over the shirt; 'big': only the big colours."""
    im = im.convert("RGBA")
    scale = WORK / max(im.size)
    small = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS) if scale < 1 else im
    scale = min(scale, 1.0)
    a = rgb_array(small)
    g = filled_garment_mask(a)
    ys, xs = np.nonzero(g)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    spread, big = find_fabric_colours(a), find_fabric_colours(a, min_share=0.2, min_spread=0)
    pal = spread if mode == "spread" else big
    logo = g & (_distance_to(a, pal) > thr)
    # pixels where two fabric colours meet (stripe edges, panel borders) are blends, not logos, unless they are very
    # far from every fabric colour
    cls = np.argmin([np.abs(a.astype(int) - np.array(p)).sum(2) for p in pal], axis=0).astype(np.uint8)
    ci = Image.fromarray(cls)
    seam = np.array(ci.filter(ImageFilter.MaxFilter(7))) != np.array(ci.filter(ImageFilter.MinFilter(7)))
    logo &= ~(seam & (_distance_to_blends(a, pal) < thr * 0.4))
    # remove a rim along the garment outline (anti-aliasing, shading, folds on the edges)
    rim = max(7, (int(0.03 * (x1 - x0)) // 2) * 2 + 1)
    inner = np.array(Image.fromarray(g.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(rim))) > 0
    logo &= inner
    t0, t1 = find_torso_edges(g, x0, x1, y0, y1)
    return dict(
        im=im,
        a=a,
        g=g,
        logo=logo,
        pal=pal,
        fabric=spread + big,
        thr=thr,
        scale=scale,
        X0=x0,
        X1=x1,
        Y0=y0,
        Y1=y1,
        T0=t0,
        T1=t1,
        full=rgb_array(im),
    )


def _logo_alpha(crop: np.ndarray, thr: int = 90, ring: int = 4, k: int = 8, fabric=None) -> np.ndarray:
    """Alpha of a logo crop: transparent = the fabric colours found on the crop border (the cloth around the logo, also
    patterned cloth: k colours) and the blends where two of them meet; opaque = the rest. fabric: the shirt's fabric
    colours; a border colour far from them is the logo touching the crop edge (crest outline), not cloth.
    Fabric-coloured areas enclosed by the logo (red 'Bet' inside a white plate) stay opaque: only fabric connected to
    the border is cut away."""
    h, w = crop.shape[:2]
    border = np.concatenate(
        [
            crop[:ring].reshape(-1, 3),
            crop[-ring:].reshape(-1, 3),
            crop[:, :ring].reshape(-1, 3),
            crop[:, -ring:].reshape(-1, 3),
        ]
    )
    q = Image.fromarray(border[None, :, :]).quantize(k, method=Image.Quantize.MEDIANCUT)
    allp = [tuple(int(v) for v in c) for c in np.array(q.getpalette()[: 3 * k]).reshape(-1, 3)]
    pal = [
        c
        for c in allp
        if (np.abs(border.astype(int) - c).sum(1) < thr * 0.5).mean() >= 0.05
        and (fabric is None or min(np.abs(np.array(c) - p).sum() for p in fabric) <= thr * 0.7)
    ]
    pal = pal or allp[:1]
    d = _distance_to(crop, pal)
    if len(pal) > 1:
        d = np.minimum(d, _distance_to_blends(crop, pal) * 2)
    al = np.clip((d - thr * 0.5) * 255.0 / (thr * 0.5), 0, 255).astype(np.uint8)
    low = al < 128
    lab, n = label_regions(low)
    outside = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    # enclosed fabric-coloured parts: letters inside a plate stay; the holes of letters (o, e, P) are small and stay
    # transparent, else the cloth photographed through them would be pasted on the kit
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    big = sizes >= 0.006 * h * w
    al[low & ~np.isin(lab, list(outside)) & big[lab]] = 255
    return al


def _candidate(ctx: dict, comp: np.ndarray, keep: np.ndarray | None = None) -> dict:
    """Candidate dict for the work-size mask comp. keep: work-size mask limiting the alpha (join)."""
    im, scale, pal, thr, full = ctx["im"], ctx["scale"], ctx["pal"], ctx["thr"], ctx["full"]
    gx0, gy0, gw, gh = ctx["X0"], ctx["Y0"], ctx["X1"] - ctx["X0"], ctx["Y1"] - ctx["Y0"]
    t0, t1 = ctx["T0"], ctx["T1"]
    cy_, cx_ = np.nonzero(comp)
    x0, x1, y0, y1 = cx_.min(), cx_.max() + 1, cy_.min(), cy_.max() + 1
    pad = 4
    bx = [
        max(0, int((x0 - pad) / scale)),
        max(0, int((y0 - pad) / scale)),
        min(im.width, int((x1 + pad) / scale)),
        min(im.height, int((y1 + pad) / scale)),
    ]
    crop = full[bx[1] : bx[3], bx[0] : bx[2]]
    if keep is None:
        al = _logo_alpha(crop, thr, fabric=ctx["fabric"])
    else:  # join: the kept parts may touch the crop edge, so the border is not pure fabric; the mask decides
        al = np.clip((_distance_to(crop, pal) - thr * 0.5) * 255.0 / (thr * 0.5), 0, 255).astype(np.uint8)
        k = Image.fromarray(keep.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))
        k = np.array(k.resize((im.width, im.height), Image.NEAREST))[bx[1] : bx[3], bx[0] : bx[2]]
        al = np.minimum(al, k)
    return {
        "image": Image.fromarray(np.dstack([crop, al]), "RGBA"),
        "box": bx,
        "cx": ((x0 + x1) / 2 - gx0) / gw,
        "cy": ((y0 + y1) / 2 - gy0) / gh,
        "w": (x1 - x0) / gw,
        "h": (y1 - y0) / gh,
        # the same, relative to the torso (sleeves excluded): used to place the logo on the texture
        "tx": ((x0 + x1) / 2 - t0) / (t1 - t0),
        "tw": (x1 - x0) / (t1 - t0),
    }


def _panel_logos(ctx: dict, comp: np.ndarray, join: int, min_px: float) -> list[np.ndarray]:
    """Logos sitting on a tall panel (Crotone home: maker and crest on red stripes): the panel's own colour is fabric
    too. Returns the logo parts inside it, [] if the panel holds none, or the panel itself if it is not one plain
    colour (e.g. a stroke crossing letters)."""
    a, thr = ctx["a"], ctx["thr"]
    px = Image.fromarray(a[comp][None, :, :])
    cols = np.array(px.quantize(4, method=Image.Quantize.MEDIANCUT).getpalette()[:12]).reshape(-1, 3)
    near = [(np.abs(a[comp].astype(int) - c).sum(1) < thr * 0.6).mean() for c in cols]
    dom = cols[int(np.argmax(near))]
    if max(near) < 0.5:
        return [comp]
    inner = np.array(Image.fromarray(comp.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(5))) > 0
    sub = comp & inner & (np.abs(a.astype(int) - dom).sum(2) > thr)
    return [p for p in _components(sub, join) if p.sum() >= min_px]


def _find_pass(im, mode="spread", thr=90, join=9, min_area=0.0004, max_w=0.7) -> list[dict]:
    """Candidates of one pass: [{'image': RGBA, 'cx', 'cy', 'w', 'h' (fractions of the garment box), 'tx', 'tw'
    (torso), 'box'}]."""
    ctx = analyse_garment(im, mode, thr)
    a, g, logo = ctx["a"], ctx["g"], ctx["logo"]
    gw, garea = ctx["X1"] - ctx["X0"], g.sum()
    # a component wider than max_w is fabric (bands, shoulder panels) or logos glued to dark side panels by the
    # dilation: split it by the colour of its pixels and keep the parts that are logo-sized
    comps = []
    for comp in _components(logo, join):
        if _width(comp) <= max_w * gw:
            comps.append(comp)
            continue
        px = Image.fromarray(a[comp][None, :, :])
        cols = np.array(px.quantize(6, method=Image.Quantize.MEDIANCUT).getpalette()[:18]).reshape(-1, 3)
        cl = np.argmin([np.abs(a.astype(int) - c).sum(2) for c in cols], axis=0)
        for i in range(len(cols)):
            comps += [p for p in _components(comp & (cl == i), join) if _width(p) <= max_w * gw]
    gh = ctx["Y1"] - ctx["Y0"]
    final = []
    for comp in comps:  # a tall stripe or panel not spread enough to count as fabric: look inside it
        tall = comp.sum() >= 0.01 * garea and np.ptp(np.nonzero(comp.any(1))[0]) > 0.2 * gh
        final += _panel_logos(ctx, comp, join, min_area * garea) if tall else [comp]
    return [_candidate(ctx, comp) for comp in final if comp.sum() >= min_area * garea]


def find_logos(im: Image.Image, limit: int = 16, **kw) -> list[dict]:
    """Logo candidates of a shirt photo, chest logos first and edge pieces (collar, cuffs, side panels) last. Union
    of two passes: fabric = colours spread over the shirt (finds white sponsors on stripes), and fabric = only the big
    colours (finds dark sponsors near dark panels); overlapping boxes merged."""
    out = []
    for mode in ("spread", "big"):
        for c in _find_pass(im, mode=mode, **kw):
            _merge(out, c)
    out = _drop_unions_and_fragments(out)
    out.sort(key=lambda c: abs(c["cx"] - 0.5) * 1.5 + abs(c["cy"] - 0.35) + (0.5 if c["h"] > 2 * c["w"] else 0))
    return out[:limit]


def logo_role(c: dict, side: str = "front") -> str:
    """What a candidate is, from where it sits on the torso (tx, tw: torso fractions; cy: garment height): front:
    'maker' (upper left chest), 'crest' (upper right), 'sponsor' (centred, chest or belly); back: 'sponsor' (centred);
    everything else 'other' (sleeves, collar, hem, fragments, strokes)."""
    tx, tw, cy = c["tx"], c["tw"], c["cy"]
    if tx - tw / 2 < -0.05 or tx + tw / 2 > 1.05 or tw < 0.06 or c["h"] > 2 * c["w"]:
        return "other"
    if side == "back":
        return "sponsor" if 0.1 <= cy <= 0.92 and abs(tx - 0.5) <= 0.12 else "other"
    if cy < 0.12 or cy > 0.8:
        return "other"
    if cy < 0.33 and tw < 0.3:
        if tx < 0.45:
            return "maker"
        if tx > 0.55:
            return "crest"
    return "sponsor" if abs(tx - 0.5) <= 0.12 and cy >= 0.25 else "other"


def join_logos(im: Image.Image, boxes, inside: float = 0.7, thr: int = 90, clip: bool = False) -> dict:
    """One logo from several candidate boxes (full-size pixel boxes): the parts of the logo mask that lie mostly
    (inside share of their pixels) in the union box. Strokes crossing the logo in the same colour run far out of the
    box and are dropped; with clip, parts crossing the box edge are cut at the edge instead (letters touching a
    stroke). Raises PhotoKitError when nothing lies inside the boxes."""
    ctx = analyse_garment(im, "big", thr)
    s = ctx["scale"]
    u = [
        min(b[0] for b in boxes) * s,
        min(b[1] for b in boxes) * s,
        max(b[2] for b in boxes) * s,
        max(b[3] for b in boxes) * s,
    ]
    ys, xs = np.mgrid[0 : ctx["logo"].shape[0], 0 : ctx["logo"].shape[1]]
    inbox = (xs >= u[0]) & (xs < u[2]) & (ys >= u[1]) & (ys < u[3])
    keep = np.zeros_like(ctx["logo"])
    for comp in _components(ctx["logo"], 0):
        if comp.sum() < 12:  # specks of fabric texture
            continue
        share = (comp & inbox).sum() / comp.sum()
        if share >= inside:
            keep |= comp
        elif clip and share >= 0.25:
            keep |= comp & inbox
    if not keep.any():
        raise PhotoKitError("nothing of the logo lies inside the joined boxes")
    return _candidate(ctx, keep, keep)


def _measurements(c: dict, file: str, side: str = "front") -> dict:
    m = {
        "file": file,
        "box": [int(v) for v in c["box"]],
        **{k: round(float(c[k]), 4) for k in ("cx", "cy", "w", "h", "tx", "tw")},
    }
    m["role"] = logo_role(m, side)
    return m


def candidates_path(out_dir: str, stem: str) -> str:
    return os.path.join(out_dir, f"_candidates_{stem}.json")


def cut_logos(photo: str, out_dir: str) -> list[str]:
    """Cuts every logo candidate of a shirt photo into out_dir (<stem>_cNN.png) and writes their measurements
    (_candidates_<stem>.json); returns the files written, best candidates first."""
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(photo))[0]
    side = photo_side(photo)
    files, meta = [], []
    for i, cd in enumerate(find_logos(Image.open(photo)), 1):
        name = f"{stem}_c{i:02d}.png"
        cd["image"].save(os.path.join(out_dir, name))
        files.append(os.path.join(out_dir, name))
        meta.append(_measurements(cd, name, side))
    with open(candidates_path(out_dir, stem), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return files


def join_candidates(photo: str, numbers: list[int], out_dir: str, clip: bool = False) -> str:
    """Joins candidates (numbers from 1, as cut_logos numbered them) of a photo into <stem>_jNN-NN.png, recorded in
    the candidates' json (a redo replaces the old one); returns the file written."""
    stem = os.path.splitext(os.path.basename(photo))[0]
    js = candidates_path(out_dir, stem)
    with open(js, encoding="utf-8") as f:
        meta = json.load(f)
    c = join_logos(Image.open(photo), [meta[n - 1]["box"] for n in numbers], clip=clip)
    name = "%s_j%s.png" % (stem, "-".join("%02d" % n for n in numbers))
    c["image"].save(os.path.join(out_dir, name))
    meta = [m for m in meta if m["file"] != name] + [_measurements(c, name, photo_side(photo))]
    with open(js, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return os.path.join(out_dir, name)
