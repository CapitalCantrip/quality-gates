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
    suffixes: tuple
    counter: str
    coverage_from: str
    lizard_languages: tuple
    coverage: tuple
    cc_check: bool
    cc_check_nothing_found: Optional[str]

    @property
    def scope(self) -> str:
        return f"{self.label}-only"

    @property
    def suffix_text(self) -> str:
        return " ".join(self.suffixes)


LANGUAGES = {
    "python": Language(
        label="Python",
        suffixes=(".py",),
        counter=RADON,
        coverage_from="`coverage json`",
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
        suffixes=(".swift",),
        counter=LIZARD,
        coverage_from="an Xcode .xcresult bundle via xcrun xccov, or the llvm-cov export JSON a SwiftPM package's tests write",
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
                 " (path from `swift test --show-codecov-path`), measured in this checkout",
            read=llvm_cov.read,
        )),
        cc_check=False,
        cc_check_nothing_found=None,
    ),
    "typescript": Language(
        label="TypeScript",
        suffixes=(".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"),
        counter=LIZARD,
        coverage_from="Istanbul's coverage-final.json, written by Vitest and Jest",
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
