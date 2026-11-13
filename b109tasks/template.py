"""A tiny text template engine.

Syntax::

    Hello {{ user.name|title }}!
    {% if user.admin %}You are an admin.{% else %}Welcome.{% endif %}

* ``{{ expr }}`` prints a value. ``expr`` is a dotted path looked up in the
  context (dict keys first, then attributes), optionally followed by filters:
  ``upper``, ``lower``, ``title``, ``trim``, ``length``, ``join:", "`` and
  ``default:"text"``.
* Output is HTML-escaped unless the template is rendered with
  ``autoescape=False``.
* ``{% if expr %}`` / ``{% if not expr %}`` with optional ``{% else %}``;
  blocks nest. A name that does not exist counts as false in a condition.
* ``{% for item in items %}...{% endfor %}`` repeats its body for each
  element. Inside the body, ``loop.index`` (from 1), ``loop.first`` and
  ``loop.last`` describe the current iteration. The loop variable and
  ``loop`` exist only inside the body; loops nest.
* Printing a name that does not exist raises :class:`UndefinedError`, unless
  the ``default`` filter is applied.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Template", "TemplateSyntaxError", "UndefinedError", "render"]

_TOKEN = re.compile(r"({{.*?}}|{%.*?%})", re.DOTALL)
_FILTER = re.compile(r'^(\w+)(?::"(.*)")?$', re.DOTALL)


_MISSING = object()


class TemplateSyntaxError(ValueError):
    pass


class UndefinedError(LookupError):
    pass


@dataclass
class _Var:
    path: str
    filters: list[tuple[str, str | None]]


@dataclass
class _If:
    path: str
    negate: bool
    body: list[Any] = field(default_factory=list)
    orelse: list[Any] = field(default_factory=list)


@dataclass
class _For:
    var: str
    path: str
    body: list[Any] = field(default_factory=list)


def _resolve(context: Mapping[str, Any], path: str) -> Any:
    head, *rest = path.split(".")
    if head not in context:
        raise UndefinedError(path)
    value = context[head]
    for part in rest:
        if isinstance(value, Mapping):
            value = value[part]
        else:
            value = getattr(value, part)
    return value


def _apply_filter(value: Any, name: str, arg: str | None) -> Any:
    if name == "upper":
        return str(value).upper()
    if name == "lower":
        return str(value).lower()
    if name == "title":
        return str(value).title()
    if name == "trim":
        return str(value).strip()
    if name == "length":
        return len(value)
    if name == "join":
        return (arg if arg is not None else "").join(str(v) for v in value)
    if name == "default":
        return arg if value is None or value == "" else value
    raise TemplateSyntaxError(f"unknown filter {name!r}")


def _parse_var(source: str) -> _Var:
    path, *raw_filters = [p.strip() for p in source.split("|")]
    if not re.fullmatch(r"[A-Za-z_]\w*(\.\w+)*", path):
        raise TemplateSyntaxError(f"bad expression {source!r}")
    filters = []
    for raw in raw_filters:
        m = _FILTER.match(raw)
        if not m:
            raise TemplateSyntaxError(f"bad filter {raw!r}")
        filters.append((m[1], m[2]))
    return _Var(path, filters)


class Template:
    def __init__(self, source: str) -> None:
        self.source = source
        self._nodes = self._parse(_TOKEN.split(source))

    @staticmethod
    def _parse(tokens: list[str]) -> list[Any]:
        root: list[Any] = []
        stack: list[tuple[_If | _For, list[Any]]] = []
        current = root
        for token in tokens:
            if token.startswith("{{"):
                current.append(_parse_var(token[2:-2].strip()))
            elif token.startswith("{%"):
                words = token[2:-2].split()
                if not words:
                    raise TemplateSyntaxError("empty tag")
                if words[0] == "if":
                    negate = len(words) == 3 and words[1] == "not"
                    if len(words) != (3 if negate else 2):
                        raise TemplateSyntaxError(f"bad if tag {token!r}")
                    node: _If | _For = _If(words[-1], negate)
                    current.append(node)
                    stack.append((node, current))
                    current = node.body
                elif words[0] == "for":
                    if (len(words) != 4 or words[2] != "in"
                            or not re.fullmatch(r"[A-Za-z_]\w*", words[1])
                            or not re.fullmatch(r"[A-Za-z_]\w*(\.\w+)*", words[3])):
                        raise TemplateSyntaxError(f"bad for tag {token!r}")
                    node = _For(words[1], words[3])
                    current.append(node)
                    stack.append((node, current))
                    current = node.body
                elif words == ["else"]:
                    if not stack or not isinstance(stack[-1][0], _If):
                        raise TemplateSyntaxError("else without if")
                    current = stack[-1][0].orelse
                elif words == ["endif"]:
                    if not stack or not isinstance(stack[-1][0], _If):
                        raise TemplateSyntaxError("endif without if")
                    _, current = stack.pop()
                elif words == ["endfor"]:
                    if not stack or not isinstance(stack[-1][0], _For):
                        raise TemplateSyntaxError("endfor without for")
                    _, current = stack.pop()
                else:
                    raise TemplateSyntaxError(f"unknown tag {token!r}")
            elif token:
                current.append(token)
        if stack:
            raise TemplateSyntaxError("unclosed block")
        return root

    def render(self, context: Mapping[str, Any] | None = None, *, autoescape: bool = True) -> str:
        out: list[str] = []
        self._render(self._nodes, dict(context or {}), autoescape, out)
        return "".join(out)

    def _render(self, nodes: list[Any], ctx: dict[str, Any], esc: bool, out: list[str]) -> None:
        for node in nodes:
            if isinstance(node, str):
                out.append(node)
            elif isinstance(node, _Var):
                out.append(self._render_var(node, ctx, esc))
            elif isinstance(node, _For):
                self._render_for(node, ctx, esc, out)
            else:
                try:
                    value = bool(_resolve(ctx, node.path))
                except (UndefinedError, KeyError, AttributeError):
                    value = False
                branch = node.body if value != node.negate else node.orelse
                self._render(branch, ctx, esc, out)

    def _render_for(self, node: _For, ctx: dict[str, Any], esc: bool, out: list[str]) -> None:
        items = list(_resolve(ctx, node.path))
        saved = {name: ctx.get(name, _MISSING) for name in (node.var, "loop")}
        for i, item in enumerate(items):
            ctx[node.var] = item
            ctx["loop"] = {"index": i + 1, "first": i == 0, "last": i == len(items) - 1}
            self._render(node.body, ctx, esc, out)
        for name, value in saved.items():
            if value is _MISSING:
                ctx.pop(name, None)
            else:
                ctx[name] = value

    @staticmethod
    def _render_var(node: _Var, ctx: Mapping[str, Any], esc: bool) -> str:
        try:
            value = _resolve(ctx, node.path)
        except UndefinedError:
            if not any(name == "default" for name, _ in node.filters):
                raise
            value = None
        for name, arg in node.filters:
            value = _apply_filter(value, name, arg)
        text = "" if value is None else str(value)
        return html.escape(text) if esc else text


def render(source: str, context: Mapping[str, Any] | None = None, *, autoescape: bool = True) -> str:
    return Template(source).render(context, autoescape=autoescape)
