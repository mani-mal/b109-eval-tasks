"""Read and merge INI-like configuration.

Format::

    # comment            ; also a comment
    [section]
    key = value
    quoted = "  kept as is  "
    logs = ${paths.root}/logs     ; a reference, resolved by interpolate()

A config is a plain ``dict[str, dict[str, str]]``. Keys are case-sensitive.
A section that appears twice is merged, later keys winning.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path

__all__ = [
    "Config",
    "ConfigError",
    "dumps",
    "get",
    "get_bool",
    "get_int",
    "interpolate",
    "load_files",
    "merge",
    "parse",
]

Config = dict[str, dict[str, str]]

_MISSING = object()
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    def __init__(self, message: str, line: int | None = None) -> None:
        self.line = line
        super().__init__(f"line {line}: {message}" if line is not None else message)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse(text: str) -> Config:
    config: Config = {}
    section: dict[str, str] | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            if not line.endswith("]") or len(line) < 3:
                raise ConfigError(f"malformed section header {line!r}", lineno)
            name = line[1:-1].strip()
            section = config.setdefault(name, {})
            continue
        if "=" not in line:
            raise ConfigError(f"expected 'key = value', got {line!r}", lineno)
        if section is None:
            raise ConfigError("key outside of any section", lineno)
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            raise ConfigError("empty key", lineno)
        section[key] = _unquote(value.strip())
    return config


def merge(*configs: Mapping[str, Mapping[str, str]]) -> Config:
    """Merge configs left to right. Later values override earlier ones per key."""
    merged: Config = {}
    for config in configs:
        for name, values in config.items():
            if name in merged:
                merged[name].update(values)
            else:
                merged[name] = dict(values)
    return merged


def get(config: Mapping[str, Mapping[str, str]], section: str, key: str,
        default: object = _MISSING) -> str:
    try:
        return config[section][key]
    except KeyError:
        if default is _MISSING:
            raise KeyError(f"{section}.{key}") from None
        return default  # type: ignore[return-value]


def get_int(config: Mapping[str, Mapping[str, str]], section: str, key: str,
            default: object = _MISSING) -> int:
    value = get(config, section, key, default)
    if value is default and default is not _MISSING:
        return value  # type: ignore[return-value]
    try:
        return int(value)
    except ValueError:
        raise ConfigError(f"{section}.{key} is not an integer: {value!r}") from None


def get_bool(config: Mapping[str, Mapping[str, str]], section: str, key: str,
             default: object = _MISSING) -> bool:
    value = get(config, section, key, default)
    if value is default and default is not _MISSING:
        return value  # type: ignore[return-value]
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ConfigError(f"{section}.{key} is not a boolean: {value!r}")


_REF = re.compile(r"\$\{([^.{}]+)\.([^{}]+)\}")


def interpolate(config: Mapping[str, Mapping[str, str]]) -> Config:
    """Return a copy of ``config`` with ``${section.key}`` references resolved.

    Referenced values may contain references themselves. A reference to a
    missing key, or a cycle of references, raises ConfigError.
    """
    done: dict[tuple[str, str], str] = {}

    def resolve(section: str, key: str, chain: tuple[tuple[str, str], ...]) -> str:
        here = (section, key)
        if here in done:
            return done[here]
        if here in chain:
            path = " -> ".join(f"{s}.{k}" for s, k in chain + (here,))
            raise ConfigError(f"reference cycle: {path}")

        def substitute(m: re.Match[str]) -> str:
            ref_section, ref_key = m[1], m[2]
            if ref_key not in config.get(ref_section, {}):
                raise ConfigError(f"undefined reference {ref_section}.{ref_key} in {section}.{key}")
            return resolve(ref_section, ref_key, chain + (here,))

        value = _REF.sub(substitute, config[section][key])
        done[here] = value
        return value

    return {s: {k: resolve(s, k, ()) for k in values} for s, values in config.items()}


def dumps(config: Mapping[str, Mapping[str, str]]) -> str:
    """Serialise with sections and keys sorted, so output is stable."""
    blocks = []
    for name in sorted(config):
        lines = [f"[{name}]"]
        for key in sorted(config[name]):
            lines.append(f"{key} = {config[name][key]}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def load_files(paths: Iterable[str | Path]) -> Config:
    """Parse each existing file, merge them in order and resolve references.

    Missing files are skipped. References see the merged values, so a later
    file can override a value that an earlier file refers to.
    """
    configs = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            configs.append(parse(path.read_text(encoding="utf-8")))
    return interpolate(merge(*configs))
