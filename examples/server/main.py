"""
SERAPH governance server — examples entry point.

The server implementation lives in seraph.server so it ships with the
installed package. This module re-exports the app so existing uvicorn
invocations and the pressure test continue to work unchanged.

    uvicorn examples.server.main:app --port 8000   # still works
    uvicorn seraph.server:app --port 8000           # canonical form
    seraph-serve                                    # CLI shortcut
"""

from seraph.server import app  # noqa: F401  re-export for uvicorn
