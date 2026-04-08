from __future__ import annotations

from importlib import import_module, metadata
import inspect
from pathlib import Path
import pkgutil
from typing import Any, Callable


PackFactory = Callable[..., Any]


def list_pack_keys() -> tuple[str, ...]:
    return tuple(sorted(_discover_pack_factories().keys()))


def build_pack(pack_key: str, storage_root: str | Path = ".domaintoolbelt") -> Any:
    factories = _discover_pack_factories()
    if pack_key not in factories:
        available = ", ".join(sorted(factories)) or "<none>"
        raise ValueError(f"Unsupported domain pack: {pack_key}. Available: {available}")
    factory = factories[pack_key]
    return factory(storage_root=Path(storage_root))


def _discover_pack_factories() -> dict[str, PackFactory]:
    factories: dict[str, PackFactory] = {}
    factories.update(_builtin_pack_factories())
    factories.update(_entry_point_pack_factories())
    return factories


def _builtin_pack_factories() -> dict[str, PackFactory]:
    root = Path(__file__).resolve().parent
    factories: dict[str, PackFactory] = {}
    for module_info in pkgutil.iter_modules([str(root)]):
        module_name = module_info.name
        if module_name.startswith("_"):
            continue
        if module_name in {"__pycache__", "base", "registry"}:
            continue
        module = import_module(f"domaintoolbelt.domain_packs.{module_name}")
        factory = _extract_factory(module)
        if factory:
            factories[module_name] = factory
    return factories


def _entry_point_pack_factories() -> dict[str, PackFactory]:
    factories: dict[str, PackFactory] = {}
    try:
        entry_points = metadata.entry_points()
    except Exception:
        return factories

    if hasattr(entry_points, "select"):
        selected = entry_points.select(group="domaintoolbelt.packs")
    else:
        selected = entry_points.get("domaintoolbelt.packs", [])

    for entry_point in selected:
        try:
            loaded = entry_point.load()
        except Exception:
            continue
        factory = _coerce_factory(loaded)
        if factory:
            factories[entry_point.name] = factory
    return factories


def _extract_factory(module: Any) -> PackFactory | None:
    if callable(getattr(module, "build_pack", None)):
        return module.build_pack

    explicit = getattr(module, "PACK_CLASS", None)
    if explicit is not None:
        return _coerce_factory(explicit)

    for attribute_name in dir(module):
        if not attribute_name.endswith("Pack"):
            continue
        attribute = getattr(module, attribute_name)
        factory = _coerce_factory(attribute)
        if factory:
            return factory
    return None


def _coerce_factory(value: Any) -> PackFactory | None:
    if not callable(value):
        return None

    if inspect.isclass(value):
        return value
    return value
