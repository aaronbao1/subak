"""Frontend compatibility layer: serves the Next.js app's HttpDataClient contract under /compat/api.

Translation only (docs/frontend-alignment.md): routes call the existing services; no business rule is
duplicated here. Disabled with BACKEND_COMPAT=0.
"""
