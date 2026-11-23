"""Kits from photos: kit textures made from the product photos of a club's shirts, shorts and socks.

The steps, one module each:

- photo: what a photo shows (from its file name) and where the garment is on it;
- colour: hex colours, colours measured on a photo, contrast;
- logo: logos found on a shirt photo and cut out with their own colours;
- pattern: stripes, panels and blocks of the shirt;
- draft: a team.json drafted from the photos of a team folder (colours, logos, pattern);
- spec: team.json expanded into one spec per kit (logo positions on the texture);
- texture: a 2048x2048 kit texture painted from a spec;
- build: specs and textures of a team folder in one call;
- maker: the disk cache of makers' logos (cut from photos, recognised by their shape, reused);
- team: a team end to end, from the chosen photos to textures waiting for Deploy (crest from the game).

Naming: modules are singular nouns; public functions are verb_object (measure_zones, find_logos, paint_texture);
helpers start with an underscore. The keys of team.json and of the specs ("body", "maker_color", ...) are a file
format and keep their names.
"""


class PhotoKitError(Exception):
    """A kit cannot be made from the photos given (no shirt photo, a logo not found, ...): the message says why."""
