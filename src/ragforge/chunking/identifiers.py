"""Deterministic identities for symbols, chunk content, and emitted chunks."""

import hashlib

from ragforge.parsing.identifiers import make_symbol_key


def content_hash(content: str) -> str:
    """Hash the exact UTF-8 bytes represented by a chunk's content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_identifier(symbol_key: str, content: str, part_index: int = 0) -> str:
    """Hash symbol identity, exact content hash, and deterministic part index."""
    identity = f"{symbol_key}|{content_hash(content)}|{part_index}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def virtual_symbol_key(repository_id: str, file_path: str, purpose: str, part_index: int) -> str:
    """Give unnamed residue and baseline parts a stable file-scoped identity."""
    return make_symbol_key(
        repository_id,
        file_path,
        f"<{purpose}:{part_index}>",
        "module_content",
        part_index,
    )
