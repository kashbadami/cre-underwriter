"""
cre-underwriter — LA multifamily regulatory overlay and underwriting.

Runs on the standard library alone. No API keys, no credentials, nothing to
configure; every source it reads is public and unauthenticated. PyYAML is used
for config/statutes.yaml if it happens to be installed, and cre_underwriter
falls back to a bundled reader for the subset of YAML that file uses if it is
not — so there is no install step either way.

Every public-data adapter lives in cre_underwriter.sources and returns a
provenance-tagged result so the report can say where each number came from.
"""

__version__ = "0.1.0"
