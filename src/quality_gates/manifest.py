import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

from quality_gates import languages as registry

PACKAGE = Path(__file__).parent
COMPONENTS_PATH = PACKAGE / "components.json"
UPSTREAM_PATH = PACKAGE / "upstream.json"

ORIGIN_FIELDS = ("type", "name", "version", "changed", "adapts")
ORIGIN_TYPES = frozenset({"ours", "upstream", "dependency"})
PART_KINDS = frozenset({"skill", "hook", "baseline", "config", "ci_step", "precommit_step", "claude_md_line",
                        "command", "dependency"})
MANIFEST_REQUIRED = ("format_version", "components")
COMPONENT_REQUIRED = ("id", "name", "description", "core", "languages", "origin", "parts")
PART_REQUIRED = ("kind", "id")
ORIGIN_REQUIRED = ("type",)
RECORD_REQUIRED = ("sources",)
SOURCE_REQUIRED = ("repo", "commit", "copied", "files")
ONE_SENTENCE = r"^[^\n]+\.$"


class ManifestError(Exception):
    pass


@dataclass(frozen=True)
class Origin:
    type: str
    name: Optional[str] = None
    version: Optional[str] = None
    changed: Optional[bool] = None
    adapts: Optional[Tuple[str, ...]] = None

    def as_dict(self):
        values = {key: getattr(self, key) for key in ORIGIN_FIELDS}
        return {key: list(value) if key == "adapts" else value for key, value in values.items() if value is not None}


@dataclass(frozen=True)
class Part:
    kind: str
    id: str
    origin: Optional[Origin] = None
    languages: Optional[Tuple[str, ...]] = None
    marker: Optional[str] = None
    found_in: Optional[str] = None
    file: Optional[str] = None


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    description: str
    core: bool
    languages: Tuple[str, ...]
    origin: Origin
    parts: Tuple[Part, ...]

    def origin_of(self, part):
        return part.origin or self.origin


@dataclass(frozen=True)
class Manifest:
    format_version: int
    components: Tuple[Component, ...]


@dataclass(frozen=True)
class Source:
    repo: str
    commit: str
    copied: str
    files: Mapping[str, str]


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as error:
        raise ManifestError(f"{path}: not valid JSON: {error}") from error


def fail_unless(holds, message):
    if not holds:
        raise ManifestError(message)


def unique(keys, where, what):
    seen = set()
    for key in keys:
        fail_unless(key not in seen, f"{where}: {what(key)} is listed twice")
        seen.add(key)


def require(data, fields, where):
    if not isinstance(data, dict):
        raise ManifestError(f"{where}: expected an object")
    for field in fields:
        if field not in data:
            raise ManifestError(f"{where}: missing field '{field}'")
    return data


def known(value, allowed, what, where):
    if value not in allowed:
        raise ManifestError(f"{where}: unknown {what} '{value}'")
    return value


def labelled(data, noun, number):
    if isinstance(data, dict) and isinstance(data.get("id"), str):
        return f"{noun} '{data['id']}'"
    return f"{noun} {number}"


def known_languages(values, where):
    return tuple(known(value, registry.LANGUAGES, "language", where) for value in values)


def optional_languages(value, where):
    return None if value is None else known_languages(value, where)


def optional_tuple(value):
    return None if value is None else tuple(value)


def origin_from(data, where):
    require(data, ORIGIN_REQUIRED, where)
    return Origin(known(data["type"], ORIGIN_TYPES, "origin type", where), data.get("name"), data.get("version"),
                  data.get("changed"), optional_tuple(data.get("adapts")))


def part_from(data, where):
    require(data, PART_REQUIRED, where)
    origin = data.get("origin")
    return Part(known(data["kind"], PART_KINDS, "part kind", where), data["id"],
                None if origin is None else origin_from(origin, where), optional_languages(data.get("languages"), where),
                data.get("marker"), data.get("found_in"), data.get("file"))


def check_component_fields(data, where):
    require(data, COMPONENT_REQUIRED, where)
    fail_unless(isinstance(data["core"], bool), f"{where}: field 'core' must be true or false")
    fail_unless(isinstance(data["languages"], list), f"{where}: field 'languages' must be a list")
    fail_unless(isinstance(data["description"], str) and re.search(ONE_SENTENCE, data["description"]) is not None,
                f"{where}: the description must be one line ending in a full stop")


def component_from(data, where):
    check_component_fields(data, where)
    found = enumerate(data["parts"], 1)
    component = Component(data["id"], data["name"], data["description"], data["core"], known_languages(data["languages"], where),
                          origin_from(data["origin"], where),
                          tuple(part_from(p, f"{where}, {labelled(p, 'part', n)}") for n, p in found))
    unique(((p.kind, p.id) for p in component.parts), where, lambda key: f"part {key[0]} '{key[1]}'")
    return component


def components_from(data, name=COMPONENTS_PATH.name):
    require(data, MANIFEST_REQUIRED, name)
    version = data["format_version"]
    fail_unless(isinstance(version, int) and not isinstance(version, bool),
                f"{name}: field 'format_version' must be a whole number")
    found = enumerate(data["components"], 1)
    components = tuple(component_from(c, f"{name}: {labelled(c, 'component', n)}") for n, c in found)
    unique((c.id for c in components), name, lambda key: f"component id '{key}'")
    return Manifest(version, components)


def source_from(data, where):
    require(data, SOURCE_REQUIRED, where)
    return Source(data["repo"], data["commit"], data["copied"], dict(data["files"]))


def sources_from(data, name=UPSTREAM_PATH.name):
    require(data, RECORD_REQUIRED, name)
    return tuple(source_from(s, f"{name}: source {n}") for n, s in enumerate(data["sources"], 1))


def load_components(path=COMPONENTS_PATH):
    return components_from(read_json(path), Path(path).name)


def load_sources(path=UPSTREAM_PATH):
    return sources_from(read_json(path), Path(path).name)
