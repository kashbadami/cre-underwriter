"""
Provenance tagging.

Every value that reaches the report carries one of these tags. The point is that
a reader can look at any number in the output and know, without reading the code,
whether the tool fetched it, computed it, was handed it, or made it up.

Nothing in this codebase is allowed to produce a bare number.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# Tag vocabulary. Keep this list short — a long list is a list nobody reads.
AUTO = "auto"          # fetched live from a named public source this run
INPUT = "input"        # supplied by the user on the command line or in a JSON file
DERIVED = "derived"    # computed from other tagged values in this report
MANUAL = "manual"      # NOT available programmatically; a human must look it up
DEFAULT = "default"    # a placeholder assumption the tool supplied. Always suspect.
MISSING = "missing"    # needed, not available, and no default was safe to invent

_LABEL = {
    AUTO: "auto",
    INPUT: "input",
    DERIVED: "derived",
    MANUAL: "MANUAL",
    DEFAULT: "DEFAULT — assumption",
    MISSING: "MISSING",
}


@dataclass
class Value:
    """A number or string plus where it came from."""

    value: Any
    tag: str
    source: Optional[str] = None      # URL or short source name
    checked: Optional[str] = None     # ISO date the source was last verified
    note: Optional[str] = None        # anything the reader needs in order to trust it

    def __post_init__(self) -> None:
        if self.tag not in _LABEL:
            raise ValueError(f"unknown provenance tag: {self.tag!r}")

    # -- convenience ------------------------------------------------------

    @property
    def is_known(self) -> bool:
        return self.tag != MISSING and self.value is not None

    @property
    def is_assumption(self) -> bool:
        """True when the number is ours, not the world's."""
        return self.tag in (DEFAULT, MISSING)

    def label(self) -> str:
        bits = [_LABEL[self.tag]]
        if self.source:
            bits.append(self.source)
        if self.checked:
            bits.append(f"checked {self.checked}")
        return " · ".join(bits)

    def as_dict(self) -> dict:
        d = {"value": self.value, "provenance": self.tag}
        if self.source:
            d["source"] = self.source
        if self.checked:
            d["checked"] = self.checked
        if self.note:
            d["note"] = self.note
        return d

    def __float__(self) -> float:
        return float(self.value)


def auto(value, source, checked=None, note=None) -> Value:
    return Value(value, AUTO, source=source, checked=checked, note=note)


def user_input(value, note=None) -> Value:
    return Value(value, INPUT, note=note)


def derived(value, note=None) -> Value:
    return Value(value, DERIVED, note=note)


def manual(value, source, note=None) -> Value:
    return Value(value, MANUAL, source=source, note=note)


def default(value, note, source=None, checked=None) -> Value:
    """A placeholder. `note` is required — an unexplained default is the exact
    thing this module exists to prevent."""
    return Value(value, DEFAULT, source=source, checked=checked, note=note)


def missing(note) -> Value:
    return Value(None, MISSING, note=note)


@dataclass
class Caveat:
    """Something the reader must know before trusting a conclusion."""

    severity: str  # "blocking" | "material" | "note"
    text: str


@dataclass
class Result:
    """A source adapter's return: the data, plus what went wrong."""

    ok: bool
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    source_url: Optional[str] = None
