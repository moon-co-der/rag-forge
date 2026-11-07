import importlib.metadata
import tomllib
from pathlib import Path

import tree_sitter
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from tree_sitter import Language


def test_installed_tree_sitter_core_matches_project_constraint():
    project = Path(__file__).parents[3] / "pyproject.toml"
    dependencies = tomllib.loads(project.read_text(encoding="utf-8"))["project"]["dependencies"]
    constraint = next(item for item in dependencies if item.startswith("tree-sitter>"))
    specifier = SpecifierSet(constraint.removeprefix("tree-sitter"))
    installed = Version(importlib.metadata.version("tree-sitter"))

    assert installed in specifier, (
        f"Installed tree-sitter {installed} is outside the supported range "
        f"{specifier}; this pin avoids the native memory fault seen during symbol extraction. "
        "Reinstall the project dependencies before parsing repositories."
    )


def test_all_installed_grammar_abis_are_supported_by_the_core():
    grammars = (
        ("Python", "tree-sitter-python", tree_sitter_python.language),
        ("JavaScript", "tree-sitter-javascript", tree_sitter_javascript.language),
        ("TypeScript", "tree-sitter-typescript", tree_sitter_typescript.language_typescript),
        ("TSX", "tree-sitter-typescript", tree_sitter_typescript.language_tsx),
        ("Java", "tree-sitter-java", tree_sitter_java.language),
    )
    for label, package, grammar in grammars:
        language = Language(grammar())
        assert tree_sitter.MIN_COMPATIBLE_LANGUAGE_VERSION <= language.abi_version
        assert language.abi_version <= tree_sitter.LANGUAGE_VERSION, (
            f"{label} grammar from {package} {importlib.metadata.version(package)} uses ABI "
            f"{language.abi_version}, but tree-sitter "
            f"{importlib.metadata.version('tree-sitter')} supports ABIs "
            f"{tree_sitter.MIN_COMPATIBLE_LANGUAGE_VERSION} through "
            f"{tree_sitter.LANGUAGE_VERSION}."
        )
