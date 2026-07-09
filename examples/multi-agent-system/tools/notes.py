from __future__ import annotations

_notes: dict[str, str] = {}


def save_note(key: str, content: str) -> str:
    """Save a note under the given key."""
    _notes[key] = content
    return f"Note saved under key: {key!r}"


def read_note(key: str) -> str:
    """Read a note by key."""
    if key not in _notes:
        return f"No note found for key: {key!r}"
    return _notes[key]


def list_notes() -> str:
    """List all saved note keys."""
    if not _notes:
        return "No notes saved yet."
    return "Saved note keys: " + ", ".join(_notes.keys())
