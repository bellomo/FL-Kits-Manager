"""A team.json drafted from the photos in <team folder>\\ref (see photo.py for the file names).

Everything is measured on the photos: the colours of each kit, the maker logo (the photo's graphic, position, size),
the crest's position and size (the crest file stays the game's one), the chest and back sponsors, and the stripes and
panels of the body. Each kit gets a "_draft" entry with the photos used, the parts deduced (no photo) and what was
found. Kits without a shirt photo are not drafted (home and away are never invented): they are listed as missing.
"""

import json
import os

from flkm.photokit import PhotoKitError
from flkm.photokit.colour import colour_distance, readable_colour, secondary_colour, measure_folder
from flkm.photokit.logo import candidates_path, cut_logos, logo_role, share_inside
from flkm.photokit.pattern import read_kit_pattern
from flkm.photokit.photo import photo_side

ORDER = ("home", "away", "third", "gk")


def draft_kit(parts: dict) -> dict | None:
    """The colours of one kit for team.json from measure_folder(...)[kit], or None without a shirt photo."""
    shirts = parts.get("shirt")
    if not shirts:
        return None
    sh = shirts[0]
    z = sh.get("zones", {})
    body = z.get("body") or sh["colours"][0][0]
    sleeve = z.get("sleeve", body)
    if colour_distance(sleeve, body) < 25:
        sleeve = body
    sec = secondary_colour(body, sh["colours"])
    collar = z.get("collar", body)
    if colour_distance(collar, body) < 25:
        collar = sec or body
    deduced, sources = [], [sh["file"]]
    if parts.get("shorts"):
        shorts = parts["shorts"][0]["colours"][0][0]
        sources.append(parts["shorts"][0]["file"])
    else:
        shorts = body
        deduced.append("shorts")
    if parts.get("socks"):
        socks = parts["socks"][0]["colours"][0][0]
        sources.append(parts["socks"][0]["file"])
    else:
        socks = shorts
        deduced.append("socks")
    if parts.get("back"):
        sources.append(parts["back"][0]["file"])
    else:
        deduced.append("back")
    text = readable_colour(body, sec)
    return {
        "body": body,
        "sleeve": sleeve,
        "cuff": collar,
        "collar": collar,
        "shorts": shorts,
        "socks": socks,
        "maker_color": text,
        "numbers": text,
        "_draft": {"sources": sources, "deduced": deduced, "secondary": sec},
    }


def _candidates(team_dir: str, photo: str) -> list[dict]:
    """Measured logo candidates of ref\\<photo> (cut first if not done yet), roles filled in for old json files. A
    joined logo (_jNN) replaces the raw candidates it overlaps."""
    stem = os.path.splitext(photo)[0]
    js = candidates_path(os.path.join(team_dir, "logos"), stem)
    if not os.path.exists(js):
        cut_logos(os.path.join(team_dir, "ref", photo), os.path.join(team_dir, "logos"))
    side = photo_side(photo)
    with open(js, encoding="utf-8") as f:
        meta = json.load(f)
    for m in meta:
        m.setdefault("role", logo_role(m, side))
    joined = [m for m in meta if "_j" in m["file"]]
    return [
        m
        for m in meta
        if m in joined
        or all(share_inside(m["box"], j["box"]) < 0.5 and share_inside(j["box"], m["box"]) < 0.5 for j in joined)
    ]


def _placed(m: dict) -> dict:
    return {"file": "logos/" + m["file"], "tx": m["tx"], "tw": m["tw"], "cy": m["cy"]}


def place_logos(team_dir: str, kit: str, parts: dict) -> tuple[dict, dict, list[str]]:
    """(team.json entries, report, notes) for one kit: maker (the photo's graphic), crest position (the crest file
    stays the game's), chest and back sponsors, body stripes and panels, all as measured on the photos of the kit."""
    out = {}
    front = _candidates(team_dir, parts["shirt"][0]["file"])
    makers = [m for m in front if m["role"] == "maker"]
    if makers:
        out["maker_logo"] = _placed(min(makers, key=lambda m: abs(m["tx"] - 0.22) + abs(m["cy"] - 0.22)))
    crests = [m for m in front if m["role"] == "crest"]
    if crests:
        c = _placed(min(crests, key=lambda m: abs(m["tx"] - 0.78) + abs(m["cy"] - 0.22)))
        out["crest_pos"] = {"from": c.pop("file"), **c}
    sp = sorted((m for m in front if m["role"] == "sponsor"), key=lambda m: m["cy"])
    if sp:
        out["chest_logos"] = [_placed(m) for m in sp]
    if parts.get("back"):
        back = _candidates(team_dir, parts["back"][0]["file"])
        bk = sorted((m for m in back if m["role"] == "sponsor"), key=lambda m: m["cy"])
        if bk:
            out["back_logos"] = [_placed(m) for m in bk]
    # big pieces in the sponsor band crossing the centre that are not sponsors: a logo split by graphic lines
    check = [
        m["file"]
        for m in front
        if m["role"] == "other"
        and m["tw"] >= 0.15
        and 0.25 <= m["cy"] <= 0.8
        and m["tx"] - m["tw"] / 2 < 0.5 < m["tx"] + m["tw"] / 2
        and -0.05 <= m["tx"] - m["tw"] / 2
    ]
    # body stripes, panels and blocks (front photo; the back photo if any, else the front mirrored); the body colour
    # stays the measured one (the pattern's median follows the shading: grey on white shirts)
    ref = os.path.join(team_dir, "ref")
    back_photo = os.path.join(ref, parts["back"][0]["file"]) if parts.get("back") else None
    pat = read_kit_pattern(os.path.join(ref, parts["shirt"][0]["file"]), back_photo)
    if pat["rects"]:
        out["rects"] = pat["rects"]
    report = {
        "maker": "maker_logo" in out,
        "crest": "crest_pos" in out,
        "sponsors": len(out.get("chest_logos", [])),
        "back": len(out.get("back_logos", [])),
        "check": check,
        "rects": len(pat["rects"]),
    }
    notes = [
        "%s: maker %s, crest %s, %d chest sponsor(s), %d back sponsor(s), %d stripe/panel rect(s)"
        % (
            kit,
            "found" if report["maker"] else "NOT FOUND",
            "found" if report["crest"] else "NOT FOUND (fixed position)",
            report["sponsors"],
            report["back"],
            report["rects"],
        )
    ]
    if check:
        notes.append(
            "%s: check %s, probably a sponsor split or crossed by lines (join the candidates)" % (kit, ", ".join(check))
        )
    return out, report, notes


def write_team_json(path: str, t: dict) -> None:
    """team.json with one line per kit (easy to compare and edit by hand)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("{\n")
        for key in [k for k in t if k != "kits"]:
            f.write(" %s: %s,\n" % (json.dumps(key), json.dumps(t[key], ensure_ascii=False)))
        f.write(' "kits": {\n')
        f.write(
            ",\n".join("  %s: %s" % (json.dumps(k), json.dumps(v, ensure_ascii=False)) for k, v in t["kits"].items())
        )
        f.write("\n }\n}\n")


def draft_team(team_dir: str, crest: str | None = None, maker: str | None = None, force: bool = False):
    """Writes team.json (team.draft.json if team.json exists, unless force) from the photos of team_dir\\ref; returns
    (the file written, the kits missing, notes). Raises PhotoKitError when there is no shirt photo."""
    res = measure_folder(os.path.join(team_dir, "ref"))
    kits, notes = {}, []
    for k in ORDER:
        kd = draft_kit(res.get(k, {}))
        if kd:
            found, kd["_draft"]["auto"], kit_notes = place_logos(team_dir, k, res[k])
            kd.update(found)
            notes += kit_notes
            kits[k] = kd
    if not kits:
        raise PhotoKitError(
            "no shirt photo in %s (names: h1/a1/t1/g1 or home_*/away_*...)" % os.path.join(team_dir, "ref")
        )
    # crest found on one kit only (e.g. glued to a stripe on another): the same place and size on the others; the same
    # for a maker hidden on a kit (in that kit's maker_color)
    seen = [kd["crest_pos"] for kd in kits.values() if "crest_pos" in kd]
    makers = [kd["maker_logo"] for kd in kits.values() if "maker_logo" in kd]
    for k, kd in kits.items():
        if seen and "crest_pos" not in kd:
            kd["crest_pos"] = dict(seen[0])
            notes.append("%s: crest position taken from %s" % (k, seen[0]["from"]))
        if makers and "maker_logo" not in kd:
            m = dict(makers[0])
            kd["maker_pos"] = {"from": m.pop("file"), **m}
            notes.append("%s: maker position taken from %s" % (k, kd["maker_pos"]["from"]))
    t = {}
    if crest:
        t["crest"] = crest
    if maker:
        t["maker"] = maker
    t["kits"] = kits
    out = os.path.join(team_dir, "team.json")
    if os.path.exists(out) and not force:
        out = os.path.join(team_dir, "team.draft.json")
    write_team_json(out, t)
    return out, [k for k in ORDER if k not in kits], notes
