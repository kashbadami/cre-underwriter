"""
Loader for config/statutes.yaml.

Two jobs beyond reading the file:

1.  Turn constants into provenance-tagged Values, so a statutory number in the
    report carries its source URL and the date it was checked, exactly like a
    number fetched over the wire.

2.  Refuse to hand out a constant that the config marks `unverified: true`
    without the caller acknowledging it. The config is honest about which
    figures were confirmed against a primary source and which were not; that
    honesty is worthless if the code quietly launders an unverified number into
    a valuation.
"""

import datetime as _dt
import os
from typing import Any, Optional

from .provenance import Caveat, Value, manual

try:  # PyYAML if present, otherwise the bundled subset reader.
    import yaml as _yaml

    def _parse(text: str) -> dict:
        return _yaml.safe_load(text)

    PARSER = "PyYAML"
except ImportError:  # pragma: no cover - depends on the host environment
    from . import _minyaml

    def _parse(text: str) -> dict:
        return _minyaml.load(text)

    PARSER = "bundled _minyaml"


DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "statutes.yaml"
)


class Statutes:
    """Read-only view over the config, with staleness and verification checks."""

    def __init__(self, data: dict, path: str):
        self.data = data
        self.path = path

    # -- construction -----------------------------------------------------

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Statutes":
        path = path or DEFAULT_PATH
        with open(path, "r", encoding="utf-8") as fh:
            return cls(_parse(fh.read()), path)

    # -- access -----------------------------------------------------------

    def section(self, name: str) -> dict:
        try:
            return self.data[name]
        except KeyError as exc:
            raise KeyError(f"no section {name!r} in {self.path}") from exc

    def get(self, section: str, key: str) -> Any:
        return self.section(section).get(key)

    def value(
        self,
        section: str,
        key: str,
        source_key: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Value:
        """A constant as a MANUAL Value.

        MANUAL, not AUTO, and the distinction is the point: this run did not
        fetch anything. A human read a statute or an agency page on the date in
        `verified` and typed the number into the config. The report should say
        so rather than implying a live lookup.
        """
        sec = self.section(section)
        if key not in sec:
            raise KeyError(f"{section}.{key} not in {self.path}")
        src = sec.get(source_key or f"{key}_source") or sec.get("source") or self.path
        v = manual(sec[key], source=src, note=note)
        v.checked = sec.get("verified")
        return v

    # -- integrity --------------------------------------------------------

    def is_unverified(self, section: str) -> bool:
        return bool(self.section(section).get("unverified"))

    def caveats(self, section: str, today: Optional[_dt.date] = None) -> list:
        """Everything a reader must be told before trusting this section."""
        sec = self.section(section)
        today = today or _dt.date.today()
        out = []

        if sec.get("unverified"):
            out.append(
                Caveat(
                    "blocking",
                    f"{sec.get('name', section)}: marked unverified in "
                    f"{os.path.basename(self.path)}. "
                    + (sec.get("unverified_note") or "").strip(),
                )
            )

        review = _as_date(sec.get("review_after"))
        if review and today > review:
            out.append(
                Caveat(
                    "material",
                    f"{sec.get('name', section)}: constants were due for review on "
                    f"{sec['review_after']} and today is {today.isoformat()}. "
                    f"Re-check {sec.get('source') or self.path} before relying on them.",
                )
            )

        if not sec.get("verified") and not sec.get("unverified"):
            out.append(
                Caveat("material", f"{sec.get('name', section)}: no verification date recorded.")
            )

        for key, text in sec.items():
            if key.endswith("_caveat") and text:
                out.append(Caveat("material", f"{sec.get('name', section)}: {text.strip()}"))
            if key.endswith("_unverified") and text is True:
                base = key[: -len("_unverified")]
                note = sec.get(f"{base}_note") or "no note recorded"
                out.append(
                    Caveat("material", f"{sec.get('name', section)}: {base} is unverified. {note}")
                )
        return out

    def all_caveats(self, sections, today: Optional[_dt.date] = None) -> list:
        out = []
        for s in sections:
            out.extend(self.caveats(s, today=today))
        return out


def _as_date(s) -> Optional[_dt.date]:
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(str(s))
    except ValueError:
        return None
