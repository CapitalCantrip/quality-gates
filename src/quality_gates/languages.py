from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

from quality_gates import coverage_json, istanbul, llvm_cov, xccov

if TYPE_CHECKING:
    from quality_gates.complexity_scan import Function

RADON = "radon"
LIZARD = "lizard"

CoverageOf = Callable[["Function"], Optional[float]]


@dataclass(frozen=True)
class CoverageFormat:
    flag: str
    source: str
    help: str
    read: Callable[[str], CoverageOf]

    @property
    def dest(self) -> str:
        return self.flag.lstrip("-").replace("-", "_")


@dataclass(frozen=True)
class Language:
    label: str
    suffixes: frozenset
    counter: str
    lizard_languages: tuple
    coverage: tuple
    cc_check: bool
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
        coverage=(CoverageFormat(
            flag="--coverage-json",
            source="coverage-json",
            help="Python: output of `coverage json`",
            read=coverage_json.read,
        ),),
        cc_check=True,
        cc_check_nothing_found="No Python files found.",
    ),
    "swift": Language(
        label="Swift",
        suffixes=frozenset({".swift"}),
        counter=LIZARD,
        lizard_languages=("swift",),
        coverage=(CoverageFormat(
            flag="--xcresult",
            source="xcresult",
            help="Swift: .xcresult bundle from xcodebuild",
            read=xccov.read,
        ), CoverageFormat(
            flag="--llvm-cov-json",
            source="llvm-cov-json",
            help="Swift: llvm-cov export JSON from SwiftPM's `swift test --enable-code-coverage`"
                 " (path from `swift test --show-codecov-path`)",
            read=llvm_cov.read,
        )),
        cc_check=False,
        cc_check_nothing_found=None,
    ),
    "typescript": Language(
        label="TypeScript",
        suffixes=frozenset({".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"}),
        counter=LIZARD,
        lizard_languages=("typescript", "tsx", "javascript", "jsx"),
        coverage=(CoverageFormat(
            flag="--istanbul-json",
            source="istanbul-json",
            help="TypeScript: Istanbul coverage-final.json from Vitest or Jest",
            read=istanbul.read,
        ),),
        cc_check=True,
        cc_check_nothing_found="No TypeScript or JavaScript functions found.",
    ),
}

COVERAGE_FORMATS = [coverage for language in LANGUAGES.values() for coverage in language.coverage]
CC_CHECK_LANGUAGES = [name for name, language in LANGUAGES.items() if language.cc_check]
