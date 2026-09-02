"""
Public-data adapters.

Each module here talks to exactly one public source and does no arithmetic.
If a source is unreachable the adapter returns Result(ok=False, error=...) and
the caller reports the failure. No adapter is permitted to substitute a guess
for a failed fetch.
"""
