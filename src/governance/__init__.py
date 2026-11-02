"""Data governance service.

Provides an authoritative record of data assets, who owns them, who may access
them, and why. Access requests move through an approval workflow, every decision
and grant is written to an append-only audit log, and asset metadata is kept
current by a sync job (Snowflake / operational sources in production) that flags
stale or incomplete entries for review.
"""

__version__ = "0.1.0"
