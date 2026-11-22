"""Kit pictures from a kit texture (any size; the zones below are measured on the 2048x2048 layout of the game's kits).

- unrolled: the texture itself, scaled.
- folded: the front and the back of the kit as it looks in the game: shirt (torso, sleeves, collar, cuffs), shorts and
  socks re-assembled from their zones of the texture. Approximate: flat shapes, no folds or shading.
"""

from PIL import Image, ImageDraw, ImageStat

VIEW_W, VIEW_H = 420, 640  # one view (front or back)
BACKGROUND = (235, 235, 235)
SKIN = (205, 160, 130)

# zones of a 2048x2048 kit texture (left, top, right, bottom)
FRONT = (738, 1040, 1310, 1870)  # front torso, collar side on top
BACK = (738, 0, 1310, 1000)  # back torso, upside down
SLEEVE_LEFT = (0, 0, 640, 560)  # cuff at the outer edge
SLEEVE_RIGHT = (1408, 0, 2048, 560)
SHORTS_LEFT = (4, 1175, 658, 1970)
SHORTS_RIGHT = (1386, 1175, 2044, 1970)
SOCKS = (4, 627, 379, 1175)
CUFF_SAMPLE = (2, 250, 24, 500)
COLLAR_SAMPLE = (700, 1880, 1300, 2040)


def perspective_coeffs(dst: list[tuple[float, float]], src: list[tuple[float, float]]) -> list[float]:
    """PIL perspective coefficients mapping the 4 output points dst to the 4 source points src"""
    rows = []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
    n = 8
    for col in range(n):  # Gauss-Jordan elimination with partial pivoting
        pivot = max(range(col, n), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) < 1e-12:
            raise ValueError("the four points do not make a quadrilateral")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        p = rows[col][col]
        rows[col] = [v / p for v in rows[col]]
        for r in range(n):
            if r != col and rows[r][col]:
                k = rows[r][col]
                rows[r] = [a - k * b for a, b in zip(rows[r], rows[col])]
    return [rows[r][n] for r in range(n)]


def _warp(canvas: Image.Image, img: Image.Image, quad: list[tuple[float, float]]) -> None:
    """paints the whole of img into quad (top left, top right, bottom right, bottom left) of canvas"""
    w, h = img.size
    c = perspective_coeffs(quad, [(0, 0), (w, 0), (w, h), (0, h)])
    out = img.convert("RGBA").transform(canvas.size, Image.PERSPECTIVE, c, Image.BICUBIC)
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).polygon(quad, fill=255)
    canvas.paste(out, (0, 0), mask)


class _Texture:
    def __init__(self, img: Image.Image):
        self.img = img.convert("RGB")
        self.scale = self.img.width / 2048

    def crop(self, box: tuple[int, int, int, int]) -> Image.Image:
        return self.img.crop(tuple(round(v * self.scale) for v in box))

    def colour(self, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
        return tuple(int(v) for v in ImageStat.Stat(self.crop(box)).median)


def unrolled(texture: Image.Image, size: int) -> Image.Image:
    return texture.convert("RGB").resize((size, size), Image.LANCZOS)


def _view(tex: _Texture, back: bool) -> Image.Image:
    w = VIEW_W
    cv = Image.new("RGBA", (w, VIEW_H), BACKGROUND + (255,))
    d = ImageDraw.Draw(cv)
    cuff, collar, body = tex.colour(CUFF_SAMPLE), tex.colour(COLLAR_SAMPLE), tex.colour(FRONT)
    # sleeves first, so that the torso covers the shoulder seam; cuffs at the open end
    left = [(125, 70), (150, 110), (95, 235), (40, 205)]
    right = [(w - 150, 110), (w - 125, 70), (w - 40, 205), (w - 95, 235)]
    if back:
        left, right = right, left
    _warp(cv, tex.crop(SLEEVE_LEFT).rotate(90, expand=True), left)
    _warp(cv, tex.crop(SLEEVE_RIGHT).rotate(-90, expand=True), right)
    for q in (left, right):
        d.line([q[2], q[3]], fill=cuff, width=14)
    # torso; on the 3D model the upper front (logos) is stretched: upper 45% of the zone -> upper 60%
    if back:
        _warp(cv, tex.crop(BACK).rotate(180), [(125, 70), (w - 125, 70), (w - 120, 400), (120, 400)])
        d.chord((170, 52, w - 170, 86), 0, 180, fill=collar)
    else:
        torso = tex.crop(FRONT)
        cut = int(torso.height * 0.45)
        _warp(cv, torso.crop((0, 0, torso.width, cut)), [(125, 70), (w - 125, 70), (w - 122, 268), (122, 268)])
        _warp(
            cv,
            torso.crop((0, cut, torso.width, torso.height)),
            [(122, 268), (w - 122, 268), (w - 120, 400), (120, 400)],
        )
        d.chord((172, 44, w - 172, 104), 0, 180, fill=tuple(int(v * 0.55) for v in body))  # inside of the shirt
        d.arc((172, 44, w - 172, 104), 0, 180, fill=collar, width=10)
    d.line([(125, 70), (190, 70)], fill=collar, width=6)
    d.line([(w - 190, 70), (w - 125, 70)], fill=collar, width=6)
    # shorts, legs and socks
    _warp(cv, tex.crop(SHORTS_LEFT), [(122, 405), (210, 405), (205, 530), (112, 520)])
    _warp(cv, tex.crop(SHORTS_RIGHT), [(210, 405), (w - 122, 405), (w - 112, 520), (215, 530)])
    socks = tex.crop(SOCKS)
    for x in (140, w - 195):
        d.rectangle((x, 530, x + 55, 570), fill=SKIN)
        _warp(cv, socks, [(x, 570), (x + 55, 570), (x + 52, 630), (x + 3, 630)])
    return cv.convert("RGB")


def folded(texture: Image.Image) -> Image.Image:
    tex = _Texture(texture)
    out = Image.new("RGB", (2 * VIEW_W, VIEW_H), BACKGROUND)
    out.paste(_view(tex, back=False), (0, 0))
    out.paste(_view(tex, back=True), (VIEW_W, 0))
    return out
