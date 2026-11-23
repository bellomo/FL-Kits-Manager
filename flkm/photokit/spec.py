"""team.json expanded into one texture spec per kit (see texture.py): logos placed on the texture.

team.json:

    {"crest": "<png>",                  the club's crest (from the game), relative to the team folder or absolute
     "maker": "puma",                   <makers folder>\\puma.png, a white-on-transparent mask (optional)
     "kits": {"home": {body, sleeve, cuff, collar, shorts, socks, [body_pattern, sleeve_pattern, rects, side_panels,
                       shorts_stripe, socks_bands, cuff_bands],
                       "maker_color", "numbers",
                       ["sponsor" / "sponsor2": {"file": "sponsor.png" | "text": "...", "color", ["box"], ["outline"],
                        ["w"], ["y"]}],
                       ["chest_logos": [{"file": "logos/home_1_c01.png", "tx", "tw", "cy"}, ...]  placed and sized
                        as measured on the photo (logo.py)],
                       ["crest_pos": {"from": "logos/home_1_c05.png", "tx", "tw", "cy"}  the crest file stays the
                        game's one, only position and width come from the crest measured on the photo],
                       ["maker_logo": {"file": "logos/home_1_c09.png", "tx", "tw", "cy"}  the maker on the chest is
                        the photo's graphic; shorts and socks get the makers mask, or a mask of the photo's logo],
                       ["maker_pos": {"from": ..., "tx", "tw", "cy"}  maker not seen on this kit's photo: the mask in
                        maker_color, placed as measured on another kit],
                       ["back_logos": [{"file": "logos/back_home_1_c01.png", "tx", "tw", "cy"}, ...]],
                       ["back_sponsor": {...} or [...]], ["back_text": {"text": "1899", "color"}],
                       ["sock_text": {"text": "SCR", "color"}], ["crest_tint"], ["maker_color_shorts"], ["maker_w"]},
              "away": {...}, "third": {...}, "gk": {...}}}
"""

import json
import os

from PIL import Image

from flkm.photokit import PhotoKitError

# photo -> texture for the front (calibrated on Catania 26/27: crest, maker and sponsor placed by hand and checked in
# the game): torso width = TORSO_PX texture pixels around x = 1024; y = Y0 + YK * cy, where cy is the logo centre as a
# fraction of the garment height on the photo (collar top = 0, hem = 1)
TORSO_PX, Y0, YK = 520, 897, 1133

# keys of a kit in team.json that are not texture spec keys
_TEAM_ONLY = {
    "maker_color",
    "sponsor",
    "sponsor2",
    "back_text",
    "back_sponsor",
    "sock_text",
    "numbers",
    "maker_w",
    "maker_color_shorts",
    "crest_tint",
    "_draft",
    "chest_logos",
    "crest_pos",
    "maker_logo",
    "maker_pos",
    "back_logos",
}


def _in_team(path: str, team_dir: str) -> str:
    return path if os.path.isabs(path) else os.path.join(team_dir, path)


def front_logo(measured: dict, team_dir: str) -> dict:
    """{"file", "tx", "tw", "cy" (from logo.py), optional "x" / "y" / "w" overrides, "color", ...} -> a texture logo
    on the front of the shirt."""
    e = {
        "x": measured.get("x", round(1024 + (measured["tx"] - 0.5) * TORSO_PX)),
        "y": measured.get("y", round(Y0 + YK * measured["cy"])),
        "w": measured.get("w", round(measured["tw"] * TORSO_PX)),
        "file": _in_team(measured["file"], team_dir),
    }
    for opt in ("color", "box", "outline", "tint"):
        if opt in measured:
            e[opt] = measured[opt]
    return e


def back_logo(measured: dict, team_dir: str) -> dict:
    """A logo measured on the back photo -> a texture logo: the back is upside down on the texture (collar seam
    ~y 1012, mirror of the front seam y 1040), so y = 1155 - YK * cy and x is mirrored around 1024."""
    e = front_logo(measured, team_dir)
    e["x"] = measured.get("x", round(1024 - (measured["tx"] - 0.5) * TORSO_PX))
    e["y"] = measured.get("y", round(1155 - YK * measured["cy"]))  # 1012 + (1040 - Y0): neck at cy = 0, like the front
    e["rotate"] = 180
    return e


def write_maker_mask(src: str, dst: str) -> str:
    """A white-on-transparent mask (like the makers' masks) of a maker logo cut out of a photo."""
    im = Image.open(src).convert("RGBA")
    out = Image.new("RGBA", im.size, (255, 255, 255, 0))
    out.putalpha(im.getchannel("A"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    out.save(dst)
    return dst


def _sponsor(sp: dict, key: str, team_dir: str) -> dict:
    e = {
        "x": 1024,
        "y": sp.get("y", 1305 if key == "sponsor" else 1430),
        "w": sp.get("w", 370 if key == "sponsor" else 260),
    }
    if "text" in sp:
        e["text"] = sp["text"]
    else:
        e["file"] = _in_team(sp["file"], team_dir)
    for opt in ("color", "box", "outline", "h", "split_x", "color_right", "font"):
        if opt in sp:
            e[opt] = sp[opt]
    if "h" in e:
        e.pop("w")
    return e


def _back_sponsor(bs: dict, team_dir: str) -> dict:
    """A sponsor on the back (the texture's back is upside down, collar ~y 1012)."""
    e = {"x": 1024, "y": bs.get("y", 890), "w": bs.get("w", 300), "rotate": 180, "color": bs["color"]}
    for opt in ("box", "outline"):
        if opt in bs:
            e[opt] = bs[opt]
    if "text" in bs:
        e["text"] = bs["text"]
    else:
        e["file"] = _in_team(bs["file"], team_dir)
    return e


def _kit_spec(name: str, k: dict, crest: str, maker_mask: str | None, team_dir: str) -> dict:
    s = {key: v for key, v in k.items() if key not in _TEAM_ONLY}
    mc = k.get("maker_color", "#ffffff")
    ms = k.get("maker_color_shorts", mc)  # maker logo on shorts and socks (e.g. white on black shorts)
    logos = [
        {"file": crest, "x": 1142, "y": 1135, "h": 108},
        {"file": crest, "x": 125, "y": 1690, "h": 70, "rotate": -90},
    ]
    cp = k.get("crest_pos")  # the game's crest, placed and sized as the crest measured on the photo
    if cp:
        e = front_logo(dict(cp, file=crest), team_dir)
        logos[0] = {"file": crest, "x": e["x"], "y": e["y"], "w": e["w"]}
    if k.get("crest_tint"):  # tonal crest: a one-colour version that keeps the crest's details
        for c in logos:
            c["tint"] = k["crest_tint"]
    ml = k.get("maker_logo")  # maker cut from the photo: real graphic and colours, measured place and size
    mp = k.get("maker_pos")  # maker not seen on this kit's photo: place and size measured on another kit
    kit_mask = maker_mask
    src = ml["file"] if ml else mp["from"] if mp else None
    if src and not (maker_mask and os.path.exists(maker_mask)):  # no mask of the maker: white mask of the photo logo
        kit_mask = write_maker_mask(_in_team(src, team_dir), os.path.join(team_dir, "logos", f"_maker_mask_{name}.png"))
    if ml:
        logos.append(front_logo(ml, team_dir))
    if kit_mask:
        if mp:
            e = front_logo(dict(mp, file=kit_mask), team_dir)
            logos.append({"file": kit_mask, "x": e["x"], "y": e["y"], "w": e["w"], "color": mc})
        elif not ml:
            logos.append({"file": kit_mask, "x": 906, "y": 1140, "w": k.get("maker_w", 100), "color": mc})
        logos += [
            {"file": kit_mask, "x": 1923, "y": 1690, "h": 70, "rotate": 90, "color": ms},
            {"file": kit_mask, "x": 80, "y": 920, "w": 56, "color": ms},
            {"file": kit_mask, "x": 1968, "y": 920, "w": 56, "color": ms},
        ]
    for key in ("sponsor", "sponsor2"):
        if k.get(key):
            logos.append(_sponsor(k[key], key, team_dir))
    logos += [front_logo(cl, team_dir) for cl in k.get("chest_logos", [])]  # front logos, placed as measured
    logos += [back_logo(bl, team_dir) for bl in k.get("back_logos", [])]  # back sponsors from the back photo
    bss = k.get("back_sponsor")
    logos += [_back_sponsor(bs, team_dir) for bs in (bss if isinstance(bss, list) else [bss] if bss else [])]
    bt = k.get("back_text")
    if bt:
        logos.append(
            {"text": bt["text"], "x": 1024, "y": 960, "h": bt.get("h", 34), "rotate": 180, "color": bt["color"]}
        )
    st = k.get("sock_text")
    if st:
        logos += [{"text": st["text"], "x": x, "y": 860, "h": 30, "color": st["color"]} for x in (80, 1968)]
    s["logos"] = logos
    s["numbers"] = k.get("numbers", "#ffffff")
    c2 = k.get("maker_color", k.get("collar", k["body"]))
    s["cfg"] = {
        "ShirtColor1": k["body"],
        "ShirtColor2": c2,
        "UndershirtColor": k.get("sleeve", k["body"]),
        "ShortsColor": k["shorts"],
        "SocksColor": k.get("socks", k["shorts"]),
        "UniColor_Color1": k["body"],
        "UniColor_Color2": c2,
    }
    return s


def expand_team(team_dir: str, makers_dir: str | None = None) -> dict[str, dict]:
    """{kit: texture spec} of the team.json in team_dir; the maker's mask comes from makers_dir (when it has one).
    Raises PhotoKitError when the crest file is missing."""
    team_dir = os.path.abspath(team_dir)  # relative paths would be doubled in the logo paths
    with open(os.path.join(team_dir, "team.json"), encoding="utf-8-sig") as f:
        t = json.load(f)
    crest = _in_team(t.get("crest", ""), team_dir) if t.get("crest") else ""
    if not os.path.isfile(crest):
        raise PhotoKitError(f"no crest file for the team: {t.get('crest') or 'none given'}")
    maker = t.get("maker")
    maker_mask = os.path.join(makers_dir, maker + ".png") if maker and makers_dir else None
    return {name: _kit_spec(name, k, crest, maker_mask, team_dir) for name, k in t["kits"].items()}
