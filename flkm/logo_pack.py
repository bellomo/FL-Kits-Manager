"""Logos in a pack (a folder or a zip, read with flkm.pack), read only.

- Pictures named as the game names them, wherever they are in the pack: e_<id>_r[_l|_ll].png is a team's crest,
  emb_<id>[_b|_w]_<l|ll>.png a variant of a competition's logo. Only the largest size of each is kept: the game's
  sizes are made from it.
- Other pictures (PNG, DDS, JPEG, WebP) named after a team or a competition (Bologna.png, Coppa Italia.jpg), compared
  like the team folders of a kit pack; a picture whose name is no team's or competition's is not a logo, nor is a
  picture in a kit folder (one with config.txt). A competition's logo found by name gives all three variants.
"""

import re
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from flkm.catalog import Competition, Team
from flkm.game import logos
from flkm.pack import Pack, PackError, _words, same_name

PICTURES = (".png", ".dds", ".jpg", ".jpeg", ".webp")
_CREST = re.compile(r"^e_(\d{6})_r(_l|_ll)?\.png$", re.IGNORECASE)
_EMBLEM = re.compile(r"^emb_(\d{4})(?:_([bw]))?_(l|ll)\.png$", re.IGNORECASE)
_RANK = {None: 0, "_l": 1, "_ll": 2, "l": 1, "ll": 2}


@dataclass(frozen=True)
class LogoFile:
    path: str  # in the pack
    kind: str  # "crest" or "emblem"
    owner: int | None  # the team or competition it goes to
    name: str  # the owner's name
    variant: str  # of a competition's logo: "", "b", "w", or "all" (one picture for the three)
    how: str  # "file name", "name", "chosen"
    sure: bool  # False: the user should check it
    note: str = ""


@dataclass(frozen=True)
class NewLogo:
    slot: str  # "crest" or "emblem", as staged
    owner: int
    name: str
    files: dict  # game path -> PNG
    source: str  # the pack file (a competition's logo: variant=path lines)


def _by_file_name(paths: list[str], teams: dict[int, Team], comps: dict[int, Competition]) -> list[LogoFile]:
    best: dict[tuple, tuple[int, str]] = {}
    for path in paths:
        name = PurePosixPath(path).name
        if m := _CREST.match(name):
            key, rank = ("crest", int(m.group(1)), ""), _RANK[m.group(2) and m.group(2).lower()]
        else:  # the paths are all crests or competition logos
            m = _EMBLEM.match(name)
            key, rank = ("emblem", int(m.group(1)), (m.group(2) or "").lower()), _RANK[m.group(3).lower()]
        if key not in best or rank > best[key][0]:
            best[key] = (rank, path)
    out = []
    for (kind, owner, variant), (_, path) in best.items():
        known = (teams if kind == "crest" else comps).get(owner)
        if known:
            out.append(LogoFile(path, kind, owner, known.name, variant, "file name", True))
        else:
            what = "team" if kind == "crest" else "competition"
            out.append(LogoFile(path, kind, None, "", variant, "file name", False, f"no {what} with id {owner}"))
    return out


def _by_name(paths: list[str], teams: list[Team], comps: list[Competition]) -> list[LogoFile]:
    owners = [("crest", t) for t in teams] + [("emblem", c) for c in comps]
    index: dict[str, list[int]] = {}  # word -> owners with it, so that only those are compared
    for i, (_, o) in enumerate(owners):
        for w in set(_words(o.name)):
            index.setdefault(w, []).append(i)
    out = []
    for path in paths:
        stem = PurePosixPath(path).stem
        words = _words(stem)
        near = sorted({i for w in words for i in index.get(w, [])})
        named = [owners[i] for i in near if same_name(stem, owners[i][1].name)]
        if not named:
            continue
        named.sort(key=lambda ko: set(_words(ko[1].name)) != set(words))  # the same words first
        kind, o = named[0]
        note = "also " + ", ".join(x.name for _, x in named[1:]) if len(named) > 1 else ""
        out.append(LogoFile(path, kind, o.id, o.name, "all" if kind == "emblem" else "", "name", not note, note))
    return out


def find(p: Pack, teams: list[Team], comps: list[Competition]) -> list[LogoFile]:
    """the logos in the pack, by their path in it"""
    paths = p.paths
    kit_folders = {str(PurePosixPath(x).parent) for x in paths if PurePosixPath(x).name.lower() == "config.txt"}
    game_named = [x for x in paths if _CREST.match(PurePosixPath(x).name) or _EMBLEM.match(PurePosixPath(x).name)]
    others = [
        x
        for x in paths
        if x.lower().endswith(PICTURES) and x not in set(game_named) and str(PurePosixPath(x).parent) not in kit_folders
    ]
    found = _by_file_name(game_named, {t.id: t for t in teams}, {c.id: c for c in comps}) + _by_name(
        others, teams, comps
    )
    return sorted(found, key=lambda f: f.path)


def to_team(f: LogoFile, team: Team) -> LogoFile:
    return replace(f, kind="crest", owner=team.id, name=team.name, variant="", how="chosen", sure=True, note="")


def to_competition(f: LogoFile, comp: Competition) -> LogoFile:
    variant = f.variant if f.kind == "emblem" else "all"
    return replace(f, kind="emblem", owner=comp.id, name=comp.name, variant=variant, how="chosen", sure=True, note="")


def label(f: LogoFile) -> str:
    """what the logo goes to: "Crest of Bologna FC (id 186)", "Coppa Italia logo (id 16), White" """
    if f.owner is None:
        return "—"
    if f.kind == "crest":
        return f"Crest of {f.name} (id {f.owner})"
    variant = "all variants" if f.variant == "all" else logos.VARIANTS[f.variant]
    return f"{f.name} logo (id {f.owner}), {variant}"


def logos_of(p: Pack, chosen: list[LogoFile], origin: str = "") -> tuple[list[NewLogo], list[str]]:
    """the files of the chosen logos, one per team or competition, and the pictures that could not be read; a picture
    for all the variants of a competition's logo fills the ones the pack has no picture of. origin: the pack's name,
    written before each path in the sources ("logos.zip: flag/e_000186_r_l.png")"""

    def where(f: LogoFile) -> str:
        return f"{origin}: {f.path}" if origin else f.path

    crests: dict[int, tuple[LogoFile, object]] = {}
    emblems: dict[int, dict[str, tuple[LogoFile, object]]] = {}
    failed = []
    for f in chosen:
        try:
            image = logos.read_picture(p.read(f.path), f.path)
        except (logos.LogoError, PackError) as e:
            failed.append(str(e))
            continue
        if f.kind == "crest":
            crests[f.owner] = (f, image)
        else:
            emblems.setdefault(f.owner, {})[f.variant] = (f, image)
    made = [NewLogo("crest", o, f.name, logos.make_crest(im, o), where(f)) for o, (f, im) in crests.items()]
    for owner, given in emblems.items():
        picked = {v: given.get(v) or given.get("all") for v in logos.VARIANTS}
        picked = {v: x for v, x in picked.items() if x}
        source = "\n".join(f"{v}={where(f)}" for v, (f, _) in picked.items())
        files = logos.make_emblem({v: im for v, (_, im) in picked.items()}, owner)
        made.append(NewLogo("emblem", owner, next(iter(picked.values()))[0].name, files, source))
    return made, failed
