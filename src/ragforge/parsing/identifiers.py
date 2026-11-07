"""Stable logical identities for parsed symbols."""

import hashlib

from ragforge.paths import normalize_repo_path


def make_symbol_key(
    repository_id: str,
    file_path: str,
    qualified_name: str,
    symbol_type: str,
    disambiguator: int = 0,
) -> str:
    """Hash repository, path, qualified name, type, and duplicate ordinal only.

    Source content is intentionally excluded so body edits preserve logical identity.
    """
    identity = "|".join(
        (
            repository_id,
            normalize_repo_path(file_path),
            qualified_name,
            symbol_type,
            str(disambiguator),
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
