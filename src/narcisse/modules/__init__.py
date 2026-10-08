"""Source modules: one file each, one `SourceModule` subclass per file, found on start-up."""

import importlib
import pkgutil

from narcisse.engine.plugin import SourceModule


def discover() -> dict[str, SourceModule]:
    """Every module of this package, by name."""
    found: dict[str, SourceModule] = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, SourceModule)
                and value is not SourceModule
                and value.__module__ == module.__name__
            ):
                instance = value()
                if instance.meta.name in found:
                    raise RuntimeError(f"two modules are named {instance.meta.name!r}")
                found[instance.meta.name] = instance
    return found
