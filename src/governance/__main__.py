import uvicorn

from .config import settings
from .db import create_all


def main() -> None:
    create_all()
    uvicorn.run("governance.app:app", host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
