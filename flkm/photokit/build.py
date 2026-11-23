"""The kit textures of a team folder in one call: team.json -> specs -> <kit>.png for every kit. Installs nothing."""

import os

from flkm.photokit.spec import expand_team
from flkm.photokit.texture import paint_texture

KITS = ("home", "away", "third", "gk")


def build_team(team_dir: str, makers_dir: str | None = None) -> dict[str, str]:
    """{kit: texture file} written in team_dir (home.png, away.png, ...) from its team.json, in kit order (other kit
    names are left out); the maker's mask comes from makers_dir. Raises PhotoKitError like spec.expand_team."""
    team_dir = os.path.abspath(team_dir)
    specs = expand_team(team_dir, makers_dir)
    done = {}
    for k in [k for k in KITS if k in specs]:
        done[k] = os.path.join(team_dir, k + ".png")
        paint_texture(specs[k], team_dir).save(done[k])
    return done
