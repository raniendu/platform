from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("raman")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
