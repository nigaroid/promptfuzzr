"""Loads PayloadSeed entries from corpus/seeds/*.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

from promptfuzzr.models import PayloadSeed, Technique


def load_seed_file(path: Path) -> list[PayloadSeed]:
    """Parse a single seeds/*.yaml file into PayloadSeed objects.

    Each YAML entry is expected to have `id`, `technique`, `base_text`,
    and optionally `tags` — see corpus/seeds/core_techniques.yaml for
    the expected shape. `technique` is validated against the
    models.Technique enum here, at load time, so a typo in a seed file
    fails loudly instead of silently producing a seed that later code
    can't match against anything.
    """
    raw = yaml.safe_load(Path(path).read_text())
    if raw is None:
        return []

    seeds: list[PayloadSeed] = []
    for entry in raw:
        try:
            technique = Technique(entry["technique"])
        except ValueError as exc:
            raise ValueError(
                f"{path}: seed '{entry.get('id', '?')}' has unknown technique "
                f"'{entry.get('technique')}' — must be one of {[t.value for t in Technique]}"
            ) from exc

        seeds.append(
            PayloadSeed(
                id=entry["id"],
                technique=technique,
                base_text=entry["base_text"].strip(),
                tags=entry.get("tags", []),
            )
        )
    return seeds


def load_seeds(seeds_dir: Path) -> list[PayloadSeed]:
    """Load and concatenate every *.yaml file under seeds_dir.

    Raises ValueError on a duplicate seed id across files — corpus
    entries need stable, unique ids since they're referenced by id
    elsewhere (e.g. `promptfuzzr seeds show <id>`, minimize --finding-id).
    """
    seeds_dir = Path(seeds_dir)
    all_seeds: list[PayloadSeed] = []
    seen_ids: dict[str, Path] = {}

    for yaml_file in sorted(seeds_dir.glob("*.yaml")):
        for seed in load_seed_file(yaml_file):
            if seed.id in seen_ids:
                raise ValueError(
                    f"duplicate seed id '{seed.id}' in {yaml_file} "
                    f"(already defined in {seen_ids[seed.id]})"
                )
            seen_ids[seed.id] = yaml_file
            all_seeds.append(seed)

    return all_seeds
