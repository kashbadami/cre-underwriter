"""
A deliberately small YAML reader.

Why this exists: the rest of the package is standard library only, and requiring
`pip install pyyaml` to read one config file is a poor trade for a tool someone
is meant to drop into a directory and run. So this parses the subset of YAML
that `config/statutes.yaml` actually uses and nothing else:

    * block mappings, nested by indentation
    * block sequences, whose items are scalars or inline flow mappings
    * inline flow mappings  { a: 1, b: null }  and flow sequences  [1, 2, 3]
    * folded block scalars  >-  and  >
    * literal block scalars |  and  |-
    * scalars: int, float, true/false, null/~, single- and double-quoted strings
    * # comments

Anything else raises. It does not silently do the wrong thing with a construct
it does not understand, which is the only property that matters here — a config
file of statutory constants that parses *almost* correctly is worse than one
that refuses to parse.

If PyYAML happens to be installed, `cre_underwriter.statutes` uses it instead
and `tests/test_minyaml.py` asserts the two agree on the real config file.
"""

import re
from typing import Any, List, Tuple


class MiniYamlError(ValueError):
    pass


_NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def load(text: str) -> Any:
    lines = _strip(text)
    if not lines:
        return {}
    value, idx = _parse_block(lines, 0, lines[0][0])
    if idx != len(lines):
        raise MiniYamlError(f"unconsumed input at line {lines[idx][2]}: {lines[idx][1]!r}")
    return value


# -- lexing ---------------------------------------------------------------


def _strip(text: str) -> List[Tuple[int, str, int]]:
    """-> [(indent, content, source_line_number)] with blanks and comments gone.

    Comment stripping is intentionally naive but safe: a '#' only starts a
    comment when it is at the start of the line or preceded by whitespace, and
    never inside quotes.
    """
    out = []
    for n, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise MiniYamlError(f"tab in indentation on line {n}")
        indent = len(raw) - len(raw.lstrip(" "))
        body = _decomment(raw.strip())
        if not body:
            continue
        out.append((indent, body, n))
    return out


def _decomment(s: str) -> str:
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()


# -- parsing --------------------------------------------------------------


def _parse_block(lines, i, indent):
    if lines[i][1].startswith("- "):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    out = {}
    while i < len(lines):
        cur_indent, body, lineno = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise MiniYamlError(f"unexpected indent on line {lineno}: {body!r}")
        if body.startswith("- "):
            break

        key, sep, rest = _split_key(body, lineno)
        if not sep:
            raise MiniYamlError(f"expected 'key: value' on line {lineno}: {body!r}")
        rest = rest.strip()
        i += 1

        if rest in (">-", ">", ">+", "|", "|-", "|+"):
            block, i = _parse_block_scalar(lines, i, indent, rest)
            out[key] = block
        elif rest == "":
            if i < len(lines) and lines[i][0] > indent:
                out[key], i = _parse_block(lines, i, lines[i][0])
            elif i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                out[key], i = _parse_seq(lines, i, indent)
            else:
                out[key] = None
        else:
            out[key] = _scalar(rest, lineno)
    return out, i


def _parse_seq(lines, i, indent):
    out = []
    while i < len(lines):
        cur_indent, body, lineno = lines[i]
        if cur_indent < indent or not body.startswith("- "):
            break
        if cur_indent > indent:
            raise MiniYamlError(f"unexpected indent on line {lineno}: {body!r}")
        item = body[2:].strip()
        i += 1
        if not item:
            raise MiniYamlError(f"empty sequence item on line {lineno}")
        out.append(_scalar(item, lineno))
    return out, i


def _parse_block_scalar(lines, i, parent_indent, style):
    """Collect the indented lines belonging to a > or | block."""
    body_lines = []
    block_indent = None
    while i < len(lines):
        cur_indent, body, _ = lines[i]
        if cur_indent <= parent_indent:
            break
        if block_indent is None:
            block_indent = cur_indent
        body_lines.append((cur_indent - block_indent) * " " + body)
        i += 1

    if style.startswith("|"):
        text = "\n".join(body_lines)
    else:
        # Folded: single newlines become spaces. The config file has no blank
        # lines inside a folded block, and _strip has dropped them anyway, so
        # this is the whole of the folding rule that applies here.
        text = " ".join(x.strip() for x in body_lines)

    if style.endswith("-"):
        return text.rstrip("\n"), i
    if style.endswith("+"):
        return text, i
    return (text.rstrip("\n") + "\n" if style.startswith("|") else text), i


def _split_key(body, lineno):
    """Split 'key: value' outside of quotes and brackets."""
    depth = 0
    quote = None
    for i, ch in enumerate(body):
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            if i + 1 < len(body) and body[i + 1] not in " \t":
                continue
            return _unquote(body[:i].strip()), True, body[i + 1 :]
    return body, False, ""


def _scalar(s, lineno):
    s = s.strip()
    if not s:
        return None
    if s[0] == "[" and s[-1] == "]":
        return [_scalar(x, lineno) for x in _split_flow(s[1:-1], lineno)] if s[1:-1].strip() else []
    if s[0] == "{" and s[-1] == "}":
        out = {}
        for part in _split_flow(s[1:-1], lineno):
            k, sep, v = _split_key(part, lineno)
            if not sep:
                raise MiniYamlError(f"bad flow mapping entry on line {lineno}: {part!r}")
            out[k] = _scalar(v, lineno)
        return out
    if s[0] in "\"'":
        if len(s) < 2 or s[-1] != s[0]:
            raise MiniYamlError(f"unterminated quoted scalar on line {lineno}: {s!r}")
        return _unquote(s)
    low = s.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if _NUM_RE.match(s):
        if re.fullmatch(r"[+-]?\d+", s):
            return int(s)
        return float(s)
    return s


def _split_flow(s, lineno):
    parts, depth, quote, buf = [], 0, None, []
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if quote:
        raise MiniYamlError(f"unterminated quote on line {lineno}")
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        inner = s[1:-1]
        if s[0] == "'":
            return inner.replace("''", "'")
        return _unescape(inner)
    return s


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", '"': '"', "\\": "\\", "/": "/"}


def _unescape(s: str) -> str:
    """Double-quoted escapes. Deliberately not the full YAML set — an escape we
    do not know raises rather than being passed through as something else.

    Note this walks characters, not bytes: a non-ASCII character in the source
    survives unchanged, which a naive unicode_escape round-trip does not.
    """
    if "\\" not in s:
        return s
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(s):
            raise MiniYamlError("trailing backslash in quoted scalar")
        nxt = s[i + 1]
        if nxt in _ESCAPES:
            out.append(_ESCAPES[nxt])
            i += 2
        elif nxt in "uU":
            width = 4 if nxt == "u" else 8
            hexes = s[i + 2 : i + 2 + width]
            if len(hexes) != width:
                raise MiniYamlError(f"bad \\{nxt} escape: {s[i:i+2+width]!r}")
            out.append(chr(int(hexes, 16)))
            i += 2 + width
        else:
            raise MiniYamlError(f"unsupported escape \\{nxt} in quoted scalar")
    return "".join(out)
