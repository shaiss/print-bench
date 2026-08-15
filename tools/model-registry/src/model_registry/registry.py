"""Parse and validate ``.github/models/registry.conf``; resolve chains.

Stdlib-only (``configparser``) and fail-loud, in the mold of
``tools/ci-gates/src/ci_gates/registry.py``: the whole file is validated eagerly
at load, and any malformed stanza — unknown kind or field, missing required
field, a model naming an undefined provider, a chain naming an undefined model —
raises ``ValueError`` with the offending stanza's id in the message.  A registry
that no one wrote must never run silently.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass

DEFAULT_PATH = ".github/models/registry.conf"

# The three stanza kinds, encoded as the section-name prefix `<kind>:<id>`.
KINDS = ("provider", "model", "chain")

# Closed field sets per kind — a typo'd field is a hard error, not a silent drop.
_PROVIDER_FIELDS = {"secret", "base_url", "notes"}
_MODEL_FIELDS = {"provider", "notes"}
_CHAIN_FIELDS = {"models"}


@dataclass(frozen=True)
class Provider:
    """An LLM provider and the (literally-referenced) secret that authenticates it."""

    id: str
    secret: str
    base_url: str = ""   # empty = the provider's native endpoint (Anthropic)
    notes: str = ""


@dataclass(frozen=True)
class Model:
    """A model hosted by exactly one provider, with required when/why notes."""

    id: str
    provider: str
    notes: str


@dataclass(frozen=True)
class Chain:
    """A named, ordered fallback chain — the thing a job routes to by name."""

    id: str
    models: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedLink:
    """One resolved chain link: the model paired with its provider's wiring."""

    position: int      # 1-based, its slot in the chain
    model: str
    provider: str
    secret: str
    base_url: str


def _split_section(name: str) -> tuple[str, str]:
    """``"provider:zai"`` -> ``("provider", "zai")``; raise on a bad shape."""
    if ":" not in name:
        raise ValueError(
            f"stanza [{name}]: section name must be '<kind>:<id>' "
            f"(kind one of {list(KINDS)})"
        )
    kind, _, ident = name.partition(":")
    kind, ident = kind.strip(), ident.strip()
    if kind not in KINDS:
        raise ValueError(f"stanza [{name}]: unknown kind {kind!r} (known: {list(KINDS)})")
    if not ident:
        raise ValueError(f"stanza [{name}]: empty id after '{kind}:'")
    return kind, ident


def _check_fields(where: str, present: set[str], allowed: set[str]) -> None:
    extra = present - allowed
    if extra:
        raise ValueError(
            f"{where}: unknown field(s) {sorted(extra)} (allowed: {sorted(allowed)})"
        )


class Registry:
    """The parsed registry: providers, models, and named chains."""

    def __init__(
        self,
        providers: dict[str, Provider],
        models: dict[str, Model],
        chains: dict[str, Chain],
    ) -> None:
        self.providers = providers
        self.models = models
        self.chains = chains

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, path: str = DEFAULT_PATH) -> "Registry":
        """Parse ``path`` into a validated Registry, or raise ``ValueError``."""
        parser = configparser.ConfigParser(
            delimiters=("=",),               # '=' only: values carry ':' (base_url)
            comment_prefixes=("#",),
            inline_comment_prefixes=None,     # '#' starts a whole-line comment only
            interpolation=None,               # values are literal — a '%' in a
                                              # `notes` string must not trigger
                                              # ConfigParser's %-interpolation (it
                                              # would raise deep in parser.items(),
                                              # past the read_file guard below).
        )
        parser.optionxform = str             # preserve key case
        # Fail loud on a genuinely malformed file rather than silently empty.
        with open(path, encoding="utf-8") as fh:
            try:
                parser.read_file(fh)
            except configparser.Error as exc:
                raise ValueError(f"{path}: malformed registry — {exc}") from exc

        providers: dict[str, Provider] = {}
        models: dict[str, Model] = {}
        chains: dict[str, Chain] = {}
        seen: set[tuple[str, str]] = set()

        for section in parser.sections():
            kind, ident = _split_section(section)
            # configparser only rejects byte-identical section names, but the id
            # is stripped, so `[model:x]` and `[model: x]` are distinct raw
            # sections that normalize to the same (kind, id) — a duplicate by the
            # registry's own id semantics. Catch it so the second can't silently
            # overwrite the first (a model misrouted to the wrong provider/secret).
            if (kind, ident) in seen:
                raise ValueError(
                    f"stanza [{section}]: duplicate {kind} id {ident!r} — another "
                    f"[{kind}:{ident}] stanza is already declared"
                )
            seen.add((kind, ident))
            fields = dict(parser.items(section))
            where = f"stanza [{section}]"
            if kind == "provider":
                _check_fields(where, set(fields), _PROVIDER_FIELDS)
                secret = fields.get("secret", "").strip()
                if not secret:
                    raise ValueError(f"{where}: 'secret' is required and must be non-empty")
                providers[ident] = Provider(
                    id=ident, secret=secret,
                    base_url=fields.get("base_url", "").strip(),
                    notes=fields.get("notes", "").strip(),
                )
            elif kind == "model":
                _check_fields(where, set(fields), _MODEL_FIELDS)
                prov = fields.get("provider", "").strip()
                if not prov:
                    raise ValueError(f"{where}: 'provider' is required")
                notes = fields.get("notes", "").strip()
                if not notes:
                    raise ValueError(
                        f"{where}: 'notes' is required — the registry must say "
                        "when/why to use each model"
                    )
                models[ident] = Model(id=ident, provider=prov, notes=notes)
            elif kind == "chain":
                _check_fields(where, set(fields), _CHAIN_FIELDS)
                raw = fields.get("models", "").strip()
                if not raw:
                    raise ValueError(f"{where}: 'models' is required and must be non-empty")
                ordered = tuple(m.strip() for m in raw.split(",") if m.strip())
                if not ordered:
                    raise ValueError(f"{where}: 'models' resolved to no ids")
                chains[ident] = Chain(id=ident, models=ordered)

        reg = cls(providers, models, chains)
        reg._validate_references()
        return reg

    def _validate_references(self) -> None:
        """Every model->provider and chain->model reference must resolve."""
        for model in self.models.values():
            if model.provider not in self.providers:
                raise ValueError(
                    f"stanza [model:{model.id}]: provider {model.provider!r} is not "
                    f"declared (known: {sorted(self.providers)})"
                )
        for chain in self.chains.values():
            for ref in chain.models:
                if ref not in self.models:
                    raise ValueError(
                        f"stanza [chain:{chain.id}]: model {ref!r} is not declared "
                        f"(known: {sorted(self.models)})"
                    )

    # -- resolution --------------------------------------------------------

    def resolve(self, chain_id: str) -> list[ResolvedLink]:
        """The chain's ordered links, each model paired with its provider wiring.

        Raises ``KeyError`` for an unknown chain (references inside a loaded
        registry are already proven to resolve by ``_validate_references``).
        """
        if chain_id not in self.chains:
            raise KeyError(f"unknown chain {chain_id!r} (known: {sorted(self.chains)})")
        links: list[ResolvedLink] = []
        for pos, model_id in enumerate(self.chains[chain_id].models, start=1):
            model = self.models[model_id]
            provider = self.providers[model.provider]
            links.append(
                ResolvedLink(
                    position=pos, model=model_id, provider=provider.id,
                    secret=provider.secret, base_url=provider.base_url,
                )
            )
        return links


def find_root(start: str = ".") -> str:
    """Walk up from ``start`` to the directory containing ``.github/models``.

    Mirrors ``tools/ci-gates`` / ``tools/lineage`` so the tool answers identically
    from anywhere in the checkout.  Returns ``start`` unchanged if not found.
    """
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".github", "models")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start)
        cur = parent
