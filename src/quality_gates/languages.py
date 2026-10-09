from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from quality_gates import coverage_json, istanbul, xccov

if TYPE_CHECKING:
    from quality_gates.complexity_scan import Function

RADON = "radon"
LIZARD = "lizard"
FLAG_PREFIX = "--"

CoverageOf = Callable[["Function"], Optional[float]]


@dataclass(frozen=True)
class CoverageFormat:
    flag: str
    help: str
    read: Callable[[str], CoverageOf]

    @property
    def dest(self) -> str:
        return self.source.replace("-", "_")

    @property
    def source(self) -> str:
        return self.flag[len(FLAG_PREFIX):]


@dataclass(frozen=True)
class Language:
    label: str
    suffixes: frozenset
    counter: str
    lizard_languages: tuple
    coverage: tuple
    cc_check_nothing_found: Optional[str]

    @property
    def scope(self) -> str:
        return f"{self.label}-only"


LANGUAGES = {
    "python": Language(
        label="Python",
        suffixes=frozenset({".py"}),
        counter=RADON,
        lizard_languages=(),
        coverage=(CoverageFormat("--coverage-json", "Python: output of `coverage json`", coverage_json.read),),
        cc_check_nothing_found="No Python files found.",
    ),
    "swift": Language(
        label="Swift",
        suffixes=frozenset({".swift"}),
        counter=LIZARD,
        lizard_languages=("swift",),
        coverage=(CoverageFormat(
            "--xcresult",
            "Swift: .xcresult bundle from xcodebuild (not SwiftPM's swift test, which produces .profdata)",
            xccov.read,
        ),),
        cc_check_nothing_found=None,
    ),
    "typescript": Language(
        label="TypeScript",
        suffixes=frozenset({".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"}),
        counter=LIZARD,
        lizard_languages=("typescript", "tsx", "javascript", "jsx"),
        coverage=(CoverageFormat(
            "--istanbul-json", "TypeScript: Istanbul coverage-final.json from Vitest or Jest", istanbul.read,
        ),),
        cc_check_nothing_found="No TypeScript or JavaScript functions found.",
    ),
}

COVERAGE_FORMATS = [coverage for language in LANGUAGES.values() for coverage in language.coverage]
CC_CHECK_LANGUAGES = [name for name, language in LANGUAGES.items() if language.cc_check_nothing_found]
