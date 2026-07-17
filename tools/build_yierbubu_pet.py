from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(r"C:\Users\admin\.codex\pets\yierbubu")
SOURCE = Path(r"C:\Users\admin\.codex\generated_images\019f6f39-d68e-7231-a126-ad079093746b\call_TKORwFNu11X1Bo7brLZolKwn.png")
ATLAS = ROOT / "spritesheet.png"
PET_JSON = ROOT / "pet.json"


def fit_cell(source: Image.Image, cell_size: tuple[int, int]) -> Image.Image:
    """Scale a pose crop into a sprite cell with transparent padding."""
    target = Image.new("RGBA", cell_size, (0, 0, 0, 0))
    fitted = ImageOps.contain(source, (cell_size[0] - 12, cell_size[1] - 12))
    x = (cell_size[0] - fitted.width) // 2
    y = (cell_size[1] - fitted.height) // 2
    target.alpha_composite(fitted, (x, y))
    return target


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    cell_w, cell_h = 192, 208

    quadrants = [
        source.crop((0, 0, 768, 1144)),
        source.crop((768, 0, 1536, 1144)),
        source.crop((0, 1144, 768, 2288)),
        source.crop((768, 1144, 1536, 2288)),
    ]
    standing = fit_cell(quadrants[0], (cell_w, cell_h))
    waving = fit_cell(quadrants[1], (cell_w, cell_h))
    hugging = fit_cell(quadrants[2], (cell_w, cell_h))
    sleepy = fit_cell(quadrants[3], (cell_w, cell_h))
    standing_flipped = ImageOps.mirror(standing)
    waving_flipped = ImageOps.mirror(waving)
    hugging_flipped = ImageOps.mirror(hugging)
    sleepy_flipped = ImageOps.mirror(sleepy)

    # Conservative atlas: every cell contains visible art to avoid empty hover frames.
    row_poses = [
        [standing] * 8,
        [standing, standing, standing, standing_flipped, standing_flipped, standing_flipped, standing, standing],
        [standing_flipped, standing_flipped, standing_flipped, standing, standing, standing, standing_flipped, standing_flipped],
        [waving] * 8,
        [standing] * 8,
        [sleepy] * 8,
        [standing, waving, standing, waving_flipped, standing, waving, standing, waving_flipped],
        [hugging, hugging, standing, standing, hugging, hugging, standing, standing],
        [sleepy, sleepy_flipped, sleepy, sleepy_flipped, sleepy, sleepy_flipped, sleepy, sleepy_flipped],
        [standing, standing_flipped, standing, standing_flipped, standing, standing_flipped, standing, standing_flipped],
        [hugging, hugging_flipped, hugging, hugging_flipped, hugging, hugging_flipped, hugging, hugging_flipped],
    ]

    atlas = Image.new("RGBA", (cell_w * 8, cell_h * 11), (0, 0, 0, 0))
    for row, poses in enumerate(row_poses):
        for col, cell in enumerate(poses):
            atlas.alpha_composite(cell, (col * cell_w, row * cell_h))

    atlas.save(ATLAS)

    pet = {
        "id": "yierbubu",
        "displayName": "一二布布",
        "description": "A two-bear companion mascot made of a warm brown bear and a white bear.",
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.png",
    }
    PET_JSON.write_text(json.dumps(pet, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
