import json
import re
from dataclasses import dataclass, replace
from datetime import date
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
MANIFEST_REQUIRED = ("format_version", "admissions", "components")
COMPONENT_REQUIRED = ("id", "name", "description", "core", "languages", "origin", "parts")
PART_REQUIRED = ("kind", "id")
STEP_KINDS = frozenset({"ci_step", "precommit_step"})
STEP_REQUIRED = ("marker",)
ORIGIN_REQUIRED = ("type",)
RECORD_REQUIRED = ("sources",)
SOURCE_REQUIRED = ("repo", "commit", "copied", "files")
SOURCE_KINDS = frozenset({"upstream", "dependency", "test-only"})
UPSTREAM_LICENCES = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"})
OSI_LICENCES = UPSTREAM_LICENCES | frozenset({
    "0BSD", "AFL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later", "Artistic-2.0", "BSL-1.0", "CDDL-1.0", "EPL-1.0", "EPL-2.0",
    "EUPL-1.2", "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later", "LGPL-2.1-only",
    "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later", "MPL-2.0", "NCSA", "OFL-1.1", "OSL-3.0", "PostgreSQL",
    "Python-2.0", "Unlicense", "Zlib",
})
ADMISSION_REQUIRED = ("name", "kind", "licence", "practice")
VERSION_FIELDS = ("minimum_version", "tested_version")
ADMISSION_FIELDS = ADMISSION_REQUIRED + ("last_release", "stable") + VERSION_FIELDS
ONE_SENTENCE = r"^[^\n]+\.$"
VERSION_FLOOR = ">="
MARKDOWN_SUFFIX = ".md"
BROKEN_EXIT = 3


class BrokenFileError(Exception):
    pass


def applies(languages, used):
    return not languages or bool(set(languages) & used)


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

    def applies_to(self, used):
        return applies(self.languages, used)


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    description: str
    core: bool
    languages: Tuple[str, ...]
    origin: Origin
    parts: Tuple[Part, ...]
    explainer: Optional[str] = None

    def applies_to(self, used):
        return applies(self.languages, used)


@dataclass(frozen=True)
class Admission:
    name: str
    kind: str
    licence: str
    practice: str
    last_release: Optional[date] = None
    stable: Optional[str] = None
    minimum_version: Optional[str] = None
    tested_version: Optional[str] = None


@dataclass(frozen=True)
class Manifest:
    format_version: int
    components: Tuple[Component, ...]
    admissions: Tuple[Admission, ...] = ()
    folder: Path = PACKAGE

    def component(self, component_id):
        return next((c for c in self.components if c.id == component_id), None)

    def explainer_path(self, component):
        return None if component.explainer is None else self.folder / component.explainer


@dataclass(frozen=True)
class Source:
    repo: str
    commit: str
    copied: str
    files: Mapping[str, str]


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise BrokenFileError(f"{path}: not found") from error
    except OSError as error:
        raise BrokenFileError(f"{path}: cannot be read: {error.strerror}") from error
    except ValueError as error:
        raise BrokenFileError(f"{path}: not valid JSON: {error}") from error


def fail_unless(holds, message):
    if not holds:
        raise BrokenFileError(message)


def unique(keys, where, what):
    seen = set()
    for key in keys:
        fail_unless(key not in seen, f"{where}: {what(key)} is listed twice")
        seen.add(key)


def require(data, fields, where):
    if not isinstance(data, dict):
        raise BrokenFileError(f"{where}: expected an object")
    for field in fields:
        if field not in data:
            raise BrokenFileError(f"{where}: missing field '{field}'")
    return data


def known(value, allowed, what, where):
    if value not in allowed:
        raise BrokenFileError(f"{where}: unknown {what} '{value}'")
    return value


def labelled(data, noun, number, key="id"):
    if isinstance(data, dict) and isinstance(data.get(key), str):
        return f"{noun} '{data[key]}'"
    return f"{noun} {number}"


def known_languages(values, where):
    for value in values:
        fail_unless(value in registry.LANGUAGES, f"{where}: unknown language '{value}'; quality-gates knows "
                                                 + ", ".join(sorted(registry.LANGUAGES)))
    return tuple(values)


def optional_tuple(data, field, where):
    value = data.get(field)
    fail_unless(value is None or isinstance(value, list), f"{where}: field '{field}' must be a list")
    return None if value is None else tuple(value)


def optional_languages(data, where):
    values = optional_tuple(data, "languages", where)
    return None if values is None else known_languages(values, where)


def origin_from(data, where):
    require(data, ORIGIN_REQUIRED, where)
    return Origin(known(data["type"], ORIGIN_TYPES, "origin type", where), data.get("name"), data.get("version"),
                  data.get("changed"), optional_tuple(data, "adapts", where))


def part_from(data, where):
    require(data, PART_REQUIRED, where)
    kind = known(data["kind"], PART_KINDS, "part kind", where)
    if kind in STEP_KINDS:
        require(data, STEP_REQUIRED, where)
    origin = data.get("origin")
    return Part(kind, data["id"], None if origin is None else origin_from(origin, where), optional_languages(data, where),
                data.get("marker"), data.get("found_in"), data.get("file"))


def check_component_fields(data, where):
    require(data, COMPONENT_REQUIRED, where)
    fail_unless(isinstance(data["core"], bool), f"{where}: field 'core' must be true or false")
    fail_unless(isinstance(data["languages"], list), f"{where}: field 'languages' must be a list")
    fail_unless(isinstance(data["description"], str) and re.search(ONE_SENTENCE, data["description"]) is not None,
                f"{where}: the description must be one line ending in a full stop")


def optional_explainer(data, where):
    value = data.get("explainer")
    fail_unless(value is None or (isinstance(value, str) and value.endswith(MARKDOWN_SUFFIX)),
                f"{where}: field 'explainer' must name a Markdown file")
    return value


def component_from(data, where):
    check_component_fields(data, where)
    found = enumerate(data["parts"], 1)
    component = Component(data["id"], data["name"], data["description"], data["core"], known_languages(data["languages"], where),
                          origin_from(data["origin"], where),
                          tuple(part_from(p, f"{where}, {labelled(p, 'part', n)}") for n, p in found),
                          optional_explainer(data, where))
    unique(((p.kind, p.id) for p in component.parts), where, lambda key: f"part {key[0]} '{key[1]}'")
    return component


def check_licence(kind, licence, where):
    fail_unless(isinstance(licence, str) and licence.strip() != "", f"{where}: field 'licence' must be a licence id")
    if kind == "upstream":
        fail_unless(licence in UPSTREAM_LICENCES,
                    f"{where}: an upstream needs one of {', '.join(sorted(UPSTREAM_LICENCES))}, not '{licence}'")
    if kind == "dependency":
        fail_unless(licence in OSI_LICENCES, f"{where}: a dependency needs an OSI-approved licence, not '{licence}'")


def release_date(value, where):
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BrokenFileError(f"{where}: field 'last_release' must be a date like 2026-10-29") from None


def check_upkeep(data, where):
    last, stable = data.get("last_release"), data.get("stable")
    fail_unless(last is not None or stable is not None, f"{where}: give either 'last_release' or 'stable'")
    fail_unless(last is None or stable is None, f"{where}: give either 'last_release' or 'stable', not both")
    released = release_date(last, where)
    fail_unless(stable is None or (isinstance(stable, str) and stable.strip() != ""),
                f"{where}: field 'stable' must give the reason")
    return released


def check_versions(data, where):
    fail_unless((data.get("minimum_version") is None) == (data.get("tested_version") is None),
                f"{where}: give 'minimum_version' and 'tested_version' together")
    for field in VERSION_FIELDS:
        fail_unless(data.get(field) is None or isinstance(data[field], str), f"{where}: field '{field}' must be text")


def admission_from(data, where):
    require(data, ADMISSION_REQUIRED, where)
    known(data["kind"], SOURCE_KINDS, "source kind", where)
    check_licence(data["kind"], data["licence"], where)
    fail_unless(isinstance(data["practice"], str) and re.search(ONE_SENTENCE, data["practice"]) is not None,
                f"{where}: the practice must be one line ending in a full stop")
    released = check_upkeep(data, where)
    check_versions(data, where)
    return replace(Admission(*(data.get(field) for field in ADMISSION_FIELDS)), last_release=released)


def admissions_from(data, name):
    found = enumerate(data, 1)
    admissions = tuple(admission_from(a, f"{name}: {labelled(a, 'admission', n, 'name')}") for n, a in found)
    unique((a.name for a in admissions), name, lambda key: f"admission name '{key}'")
    return admissions


def check_origin_admitted(origin, kinds, where):
    named = ((origin.name,) if origin.name else ()) + (origin.adapts or ())
    for source in named:
        fail_unless(source in kinds, f"{where}: origin names '{source}', which has no admission")
    if origin.name and kinds[origin.name] != origin.type:
        raise BrokenFileError(f"{where}: origin type '{origin.type}' names '{origin.name}', a {kinds[origin.name]}")


def check_component_admitted(component, kinds, name):
    where = f"{name}: component '{component.id}'"
    check_origin_admitted(component.origin, kinds, where)
    for part in component.parts:
        if part.origin is not None:
            check_origin_admitted(part.origin, kinds, f"{where}, part '{part.id}'")


def versioned(origin, minimums):
    if origin is None or origin.version is not None or minimums.get(origin.name) is None:
        return origin
    return replace(origin, version=VERSION_FLOOR + minimums[origin.name])


def with_versions(component, minimums):
    parts = tuple(replace(part, origin=versioned(part.origin, minimums)) for part in component.parts)
    return replace(component, origin=versioned(component.origin, minimums), parts=parts)


def components_from(data, name=COMPONENTS_PATH.name):
    require(data, MANIFEST_REQUIRED, name)
    version = data["format_version"]
    fail_unless(isinstance(version, int) and not isinstance(version, bool),
                f"{name}: field 'format_version' must be a whole number")
    admissions = admissions_from(data["admissions"], name)
    found = enumerate(data["components"], 1)
    components = tuple(component_from(c, f"{name}: {labelled(c, 'component', n)}") for n, c in found)
    unique((c.id for c in components), name, lambda key: f"component id '{key}'")
    kinds = {a.name: a.kind for a in admissions}
    for component in components:
        check_component_admitted(component, kinds, name)
    minimums = {a.name: a.minimum_version for a in admissions}
    return Manifest(version, tuple(with_versions(c, minimums) for c in components), admissions)


def source_from(data, where):
    require(data, SOURCE_REQUIRED, where)
    return Source(data["repo"], data["commit"], data["copied"], dict(data["files"]))


def sources_from(data, name=UPSTREAM_PATH.name):
    require(data, RECORD_REQUIRED, name)
    return tuple(source_from(s, f"{name}: source {n}") for n, s in enumerate(data["sources"], 1))


def load_components(path=COMPONENTS_PATH):
    return replace(components_from(read_json(path), Path(path).name), folder=Path(path).parent)


def load_sources(path=UPSTREAM_PATH):
    return sources_from(read_json(path), Path(path).name)
