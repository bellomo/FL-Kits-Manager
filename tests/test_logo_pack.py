"""Logos in a pack (a folder or a zip): pictures named as the game names them (e_000186_r_l.png, a team's crest;
emb_0016_w_ll.png, a variant of a competition's logo) wherever they are in the pack, the largest size of each; other
pictures named after a team or a competition (Bologna.png, Coppa Italia.png). Pictures in kit folders are kit
pictures, not logos. Then the files of the chosen logos, as the game wants them."""

import io
import zipfile

from PIL import Image

from flkm import logo_pack, pack
from flkm.catalog import Competition, Team
from flkm.game import logos

TEAMS = [
    Team(186, "Bologna FC", "BOL", "Serie A", "Italy", "UEFA"),
    Team(100, "Juventus", "JUV", "Serie A", "Italy", "UEFA"),
    Team(101, "Juventus U23", "JUV", "Serie C", "Italy", "UEFA"),
    Team(200, "Italia", "ITA", "National team", "Italy", "UEFA"),
]
COMPS = [
    Competition(16, "ITALY_D1_CUP", "Coppa Italia", "Italy", "UEFA"),
    Competition(174, "FL_UECL", "UEFA Conference League", None, None),
]


def png(side, colour=(200, 0, 0, 255)):
    buf = io.BytesIO()
    Image.new("RGBA", (side, side), colour).save(buf, "PNG")
    return buf.getvalue()


def make_pack(files):
    return pack.Pack({path: (lambda data=data: data) for path, data in files.items()})


def rows(found):
    return [(f.path, f.kind, f.owner, f.name, f.variant, f.how, f.sure, f.note) for f in found]


def test_pictures_named_as_the_game_names_them_the_largest_size_of_each():
    p = make_pack(
        {
            "Logos/common/render/symbol/flag/e_000186_r.png": png(128),
            "Logos/common/render/symbol/flag/e_000186_r_ll.png": png(512),
            "Logos/common/render/symbol/flag/e_000186_r_l.png": png(256),
            "Logos/common/render/symbol/flag/e_000186_r_euro.png": png(256),  # not one of the crest files
            "emblems/EMB_0016_W_L.PNG": png(256),
            "emblems/emb_0016_w_ll.png": png(512),
            "emblems/emb_0016_l.png": png(256),
            "emblems/emb_0999_ll.png": png(512),  # no such competition
            "flags/e_073999_r_l.png": png(256),  # no such team
            "readme.txt": b"logos",
        }
    )
    assert rows(logo_pack.find(p, TEAMS, COMPS)) == [
        ("Logos/common/render/symbol/flag/e_000186_r_ll.png", "crest", 186, "Bologna FC", "", "file name", True, ""),
        ("emblems/emb_0016_l.png", "emblem", 16, "Coppa Italia", "", "file name", True, ""),
        ("emblems/emb_0016_w_ll.png", "emblem", 16, "Coppa Italia", "w", "file name", True, ""),
        ("emblems/emb_0999_ll.png", "emblem", None, "", "", "file name", False, "no competition with id 999"),
        ("flags/e_073999_r_l.png", "crest", None, "", "", "file name", False, "no team with id 73999"),
    ]


def test_pictures_named_after_a_team_or_a_competition():
    p = make_pack(
        {
            "crests/Bologna.png": png(300),
            "crests/juventus.webp": png(300),
            "cups/Coppa Italia.jpg": png(300),
            "cups/Conference League.png": png(300),
            "photos/stadium.png": png(300),  # no team or competition with this name: not a logo
            "Bologna/p1/config.txt": b"KitFile = u0186p1",
            "Bologna/p1/u0186p1.ftex": b"kit",
            "Bologna/p1/preview.png": png(64),  # a kit folder: its pictures are not logos
            "Bologna/p1/Bologna.png": png(64),
        }
    )
    assert rows(logo_pack.find(p, TEAMS, COMPS)) == [
        ("crests/Bologna.png", "crest", 186, "Bologna FC", "", "name", True, ""),
        ("crests/juventus.webp", "crest", 100, "Juventus", "", "name", False, "also Juventus U23"),
        ("cups/Conference League.png", "emblem", 174, "UEFA Conference League", "all", "name", True, ""),
        ("cups/Coppa Italia.jpg", "emblem", 16, "Coppa Italia", "all", "name", False, "also Italia"),
    ]


def test_a_logo_can_be_given_to_a_team_or_a_competition():
    found = logo_pack.find(make_pack({"x/Bologna.png": png(64), "emb_0016_b_l.png": png(64)}), TEAMS, COMPS)
    cup, crest = found  # by their path in the pack
    assert logo_pack.to_team(crest, TEAMS[1]) == logo_pack.LogoFile(
        "x/Bologna.png", "crest", 100, "Juventus", "", "chosen", True
    )
    assert logo_pack.to_competition(crest, COMPS[1]).variant == "all"  # no variant in its name: all of them
    assert logo_pack.to_competition(cup, COMPS[1]).variant == "b"
    assert logo_pack.label(crest) == "Crest of Bologna FC (id 186)"
    assert logo_pack.label(cup) == "Coppa Italia logo (id 16), Dark"
    assert logo_pack.label(logo_pack.to_competition(crest, COMPS[0])) == "Coppa Italia logo (id 16), all variants"
    assert logo_pack.label(logo_pack.LogoFile("a.png", "crest", None, "", "", "none", False)) == "—"


def test_the_files_of_the_chosen_logos():
    p = make_pack(
        {
            "Bologna.png": png(300, (0, 0, 200, 255)),
            "emb_0016_ll.png": png(512),
            "emb_0016_w_l.png": png(256, (255, 255, 255, 255)),
            "cups/Coppa Italia.png": png(300, (0, 200, 0, 255)),
            "Conference League.png": b"not a picture",
        }
    )
    found = {f.path: f for f in logo_pack.find(p, TEAMS, COMPS)}
    chosen = [found[k] for k in ("Bologna.png", "emb_0016_ll.png", "emb_0016_w_l.png", "cups/Coppa Italia.png")]
    made, failed = logo_pack.logos_of(p, chosen + [found["Conference League.png"]])
    assert len(failed) == 1 and failed[0].startswith("Conference League.png cannot be read as a picture")
    crest, emblem = made
    assert (crest.slot, crest.owner, crest.name, crest.source) == ("crest", 186, "Bologna FC", "Bologna.png")
    assert sorted(crest.files) == sorted(logos.crest_files(186).values())
    assert (emblem.slot, emblem.owner, emblem.name) == ("emblem", 16, "Coppa Italia")
    assert sorted(emblem.files) == sorted(logos.emblem_files(16).values())  # the picture for all fills the others
    assert emblem.source == "=emb_0016_ll.png\nb=cups/Coppa Italia.png\nw=emb_0016_w_l.png"
    dark = Image.open(io.BytesIO(emblem.files[logos.emblem_files(16)[("b", 512)]]))
    white = Image.open(io.BytesIO(emblem.files[logos.emblem_files(16)[("w", 512)]]))
    assert dark.getpixel((256, 256)) == (0, 200, 0, 255) and white.getpixel((256, 256)) == (255, 255, 255, 255)


def test_logos_in_a_zip(tmp_path):
    z = tmp_path / "logos.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("pack/flag/e_000186_r_l.png", png(256))
    found = logo_pack.find(pack.open_pack(z), TEAMS, COMPS)
    assert [(f.kind, f.owner) for f in found] == [("crest", 186)]
