import re
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
    interpreters: tuple = ()

    @property
    def suffix_text(self) -> str:
        return " ".join(self.suffixes)


REGISTERED = (
    Language("python", "Python", (".py",), markers=("pyproject.toml", "setup.py")),
    Language("swift", "Swift", (".swift",), markers=("Package.swift",), folder_suffixes=(".xcodeproj",)),
    Language("typescript", "TypeScript", (".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"), markers=("package.json",)),
    Language("rust", "Rust", (".rs",), markers=("Cargo.toml",)),
    Language("shell", "Shell", (".sh", ".bash", ".zsh"), interpreters=("sh", "bash", "zsh", "dash", "ksh")),
)
SHEBANG = "#!"
ENV = "env"
ENV_SETTING = re.compile(r"[A-Za-z_]\w*=")

LANGUAGES = {language.name: language for language in REGISTERED}


def suffixes_of(names) -> tuple:
    return tuple(suffix for name in names for suffix in LANGUAGES[name].suffixes)


def language_of_file(name: str) -> Optional[str]:
    suffix = PurePath(name).suffix
    return next((language.name for language in REGISTERED if suffix in language.suffixes), None)


def language_of_folder(name: str) -> Optional[str]:
    return next((language.name for language in REGISTERED if name.endswith(language.folder_suffixes)), None)


def interpreter_of(first_line: str) -> Optional[str]:
    if not first_line.startswith(SHEBANG):
        return None
    words = first_line[len(SHEBANG):].split()
    if words and PurePath(words[0]).name == ENV:
        words = [word for word in words[1:] if not word.startswith("-") and not ENV_SETTING.match(word)]
    return PurePath(words[0]).name if words else None


def language_of_first_line(first_line: str) -> Optional[str]:
    name = interpreter_of(first_line)
    return next((language.name for language in REGISTERED if name in language.interpreters), None)


def markers_of(name: str) -> tuple:
    return LANGUAGES[name].markers
