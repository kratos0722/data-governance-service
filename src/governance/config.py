"""Runtime configuration from the environment."""

from __future__ import annotations

import os


class Settings:
    def __init__(self) -> None:
        # SQLite by default for zero-config local/dev/test; Postgres in production.
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./governance.db")
        self.port = int(os.getenv("PORT", "8000"))


settings = Settings()
