from app import models  # noqa: F401  (registers tables)
from app.db import Base, engine


def main():
    Base.metadata.create_all(engine)
    print("tables ready", flush=True)


if __name__ == "__main__":
    main()
