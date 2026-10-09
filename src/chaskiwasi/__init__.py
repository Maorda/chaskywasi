# src/chaskiwasi/__init__.py
from chaskiwasi.contract import BaseExtractionConfig
from chaskiwasi.factory import ConfigurationFactory
from chaskiwasi.main import ExtractorDocumentalUniversal

__version__ = "0.2.2"

__all__ = [
    "BaseExtractionConfig",
    "ConfigurationFactory",
    "ExtractorDocumentalUniversal",
]