import logging


def configure_logging(environment: str) -> None:
    app_level = logging.DEBUG if environment == "development" else logging.INFO
    logging.basicConfig(
        level=logging.INFO,
        format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    )
    logging.getLogger("app").setLevel(app_level)

    for logger_name in ("boto3", "botocore", "s3transfer", "urllib3", "httpx"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
