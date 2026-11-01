from dataclasses import dataclass
from pathlib import PurePath
from typing import Optional


@dataclass(frozen=True)
class Language:
    name: str
    label: str
    suffixes: tuple
    markers: tuple = ()
    folder_suffixes: tuple = ()

    @property
    def suffix_text(self) -> str:
        return " ".join(self.suffixes)


REGISTERED = (
    Language("python", "Python", (".py",), markers=("pyproject.toml", "setup.py")),
    Language("swift", "Swift", (".swift",), markers=("Package.swift",), folder_suffixes=(".xcodeproj",)),
    Language("typescript", "TypeScript", (".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"), markers=("package.json",)),
    Language("rust", "Rust", (".rs",), markers=("Cargo.toml",)),
    Language("shell", "Shell", (".sh", ".bash", ".zsh")),
)

LANGUAGES = {language.name: language for language in REGISTERED}


def suffixes_of(names) -> tuple:
    return tuple(suffix for name in names for suffix in LANGUAGES[name].suffixes)


def language_of_file(name: str) -> Optional[str]:
    suffix = PurePath(name).suffix
    return next((language.name for language in REGISTERED if suffix in language.suffixes), None)


def language_of_tracked_file(name: str) -> Optional[str]:
    return next((language.name for language in REGISTERED if name.endswith(language.suffixes)), None)


def language_of_folder(name: str) -> Optional[str]:
    return next((language.name for language in REGISTERED if name.endswith(language.folder_suffixes)), None)


def markers_of(name: str) -> tuple:
    return LANGUAGES[name].markers
