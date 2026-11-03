# Decisions

This folder holds two things.

- **The compendium**, the pages below: what is decided and true now, one page
  per question a reader asks. Read these. Each rule has exactly one home, and
  other pages point to it rather than repeating it.
- **[The archive](archive/)**: every numbered ADR as it was accepted, with its
  context, the options rejected and its addenda. Open it only to answer *why*
  something was decided, or to reorganise the compendium.

| Page | Read this when |
|---|---|
| [What gets scored](what-gets-scored.md) | a gate scores a file you did not expect, or you change `exclude`, symlink, submodule or out-of-repo handling |
| [How complexity is counted](counting-complexity.md) | you change a limit, a counter, function naming, or how `crap` reads coverage |
| [Baselines and loosening](baselines-and-loosening.md) | a gate says `PAID`, `new` or `worse`, or a project wants to relax a standard |
| [Components and setup](components-and-setup.md) | you touch a component, `qg setup`, `qg status`, `qg explain`, `/setup-standards`, the shipped skills, or an outside source |
| [How standards are made](how-standards-are-made.md) | you add or change a standard, principle or skill wording, plan a new gate, or ask the builder something |
| [Code structure](code-structure.md) | you add a module, command or file format, or wonder where new code goes |

## Changing a decision

A change is a new numbered ADR in the archive, or a dated addendum on the one
it amends, and the same pull request updates the compendium page it affects.
The compendium never says anything the archive does not back.
([ADR-012](archive/ADR-012-decisions-compendium.md))
