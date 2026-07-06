"""clinicalcompress: compress clinical text without losing clinical meaning.

Public API surface. Everything else in this package should be considered
an implementation detail unless explicitly re-exported here.
"""

from clinicalcompress.api import compress
from clinicalcompress.models import CompressionResult, ProtectedSpan, SafetyReport

__version__ = "0.1.0"
version = __version__

__all__ = [
    "compress",
    "CompressionResult",
    "ProtectedSpan",
    "SafetyReport",
    "__version__",
    "version",
]
