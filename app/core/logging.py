import logging


def configure_logging(environment: str) -> None:
    level = logging.DEBUG if environment == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )

