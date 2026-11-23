"""Team crests and competition logos: where the game keeps them (PNG files, found like any game file: livecpk roots,
then download/, then Data/ CPKs) and the files of a new one made from a picture.

- crest of a team: common/render/symbol/flag/e_<id, 6 digits>_r.png 128 px, _r_l.png 256, _r_ll.png 512; some clubs
  have a dark one for light backgrounds (_r_b, _r_b_l, _r_b_ll) and a white one (_r_w...), most of them instead of
  the plain one;
- logo of a competition: common/render/symbol/emblemLc/emb_<id, 4 digits>{,_b,_w}_{l,ll}.png 256 and 512: the
  normal logo, a dark one for light backgrounds (_b) and a white one for dark backgrounds (_w).
"""

import io
from pathlib import Path

from PIL import Image

from flkm.game.files import Found, GameFiles

FLAG = "common/render/symbol/flag/"
EMBLEM = "common/render/symbol/emblemLc/"
CREST_SIZES = {128: "", 256: "_l", 512: "_ll"}
EMBLEM_SIZES = {256: "_l", 512: "_ll"}
VARIANTS = {"": "Normal", "b": "Dark", "w": "White"}


class LogoError(ValueError):
    pass


def crest_files(team_id: int, variant: str = "") -> dict[int, str]:
    """size -> game path of the team's crest (variant: "" plain, "b" dark, "w" white)"""
    v = f"_{variant}" if variant else ""
    return {size: f"{FLAG}e_{team_id:06d}_r{v}{suffix}.png" for size, suffix in CREST_SIZES.items()}


def emblem_files(comp_id: int) -> dict[tuple[str, int], str]:
    """(variant, size) -> game path of the competition's logo"""
    return {
        (v, size): f"{EMBLEM}emb_{comp_id:04d}{'_' + v if v else ''}{suffix}.png"
        for v in VARIANTS
        for size, suffix in EMBLEM_SIZES.items()
    }


def _largest(gf: GameFiles, paths: dict[int, str]) -> Found | None:
    return next((f for size in sorted(paths, reverse=True) if (f := gf.find(paths[size]))), None)


def find_crest(gf: GameFiles, team_id: int) -> Found | None:
    """the largest crest file the game has for the team: the plain crest, else its dark or white version"""
    return next(iter(find_crests(gf, team_id).values()), None)


def find_crests(gf: GameFiles, team_id: int) -> dict[str, Found]:
    """variant ("", "b", "w") -> the largest file, of the versions of the team's crest the game has"""
    found = {v: _largest(gf, crest_files(team_id, v)) for v in VARIANTS}
    return {v: f for v, f in found.items() if f}


def with_crest_variants(gf: GameFiles, team_id: int, files: dict[str, bytes]) -> dict[str, bytes]:
    """a new crest's files, with the same picture for the dark and white versions the game has: else the game could go
    on showing those"""
    out = dict(files)
    plain = crest_files(team_id)
    for v in find_crests(gf, team_id):
        out.update({name: files[plain[size]] for size, name in crest_files(team_id, v).items()})
    return out


def find_emblem(gf: GameFiles, comp_id: int, variant: str) -> Found | None:
    """the largest file the game has for the competition's logo in that variant"""
    names = emblem_files(comp_id)
    return _largest(gf, {size: names[(variant, size)] for size in EMBLEM_SIZES})


def picture(found: Found) -> Image.Image:
    return Image.open(io.BytesIO(found.read())).convert("RGBA")


def load(path: Path) -> Image.Image:
    """a picture file (PNG, DDS, JPEG, WebP...) as RGBA"""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as e:
        raise LogoError(f"{path.name} cannot be read as a picture: {e}") from e
    return read_picture(data, path.name)


def read_picture(data: bytes, name: str) -> Image.Image:
    """a picture (PNG, DDS, JPEG, WebP...) from its bytes as RGBA; name: the file's, for the error message"""
    try:
        with Image.open(io.BytesIO(data)) as im:
            return im.convert("RGBA")
    except (OSError, ValueError) as e:
        raise LogoError(f"{name} cannot be read as a picture: {e}") from e


def _square(image: Image.Image) -> Image.Image:
    """the picture centred on a transparent square"""
    image = image.convert("RGBA")
    side = max(image.size)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return out


def _png(image: Image.Image, size: int) -> bytes:
    buf = io.BytesIO()
    image.resize((size, size), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def make_crest(image: Image.Image, team_id: int) -> dict[str, bytes]:
    """game path -> PNG of every size of the team's crest"""
    square = _square(image)
    return {name: _png(square, size) for size, name in crest_files(team_id).items()}


def make_emblem(pictures: dict[str, Image.Image], comp_id: int) -> dict[str, bytes]:
    """game path -> PNG of every size of the given variants ("", "b", "w") of the competition's logo"""
    squares = {v: _square(im) for v, im in pictures.items()}
    return {name: _png(squares[v], size) for (v, size), name in emblem_files(comp_id).items() if v in squares}
