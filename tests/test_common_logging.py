import logging

from common.logging import get_logger


def test_returns_logger() -> None:
    logger = get_logger("test.common.logging.a")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.common.logging.a"


def test_info_level() -> None:
    logger = get_logger("test.common.logging.b")
    assert logger.level == logging.INFO


def test_single_handler_on_repeated_calls() -> None:
    # Clear any leftover handlers from a prior test run.
    logging.getLogger("test.common.logging.c").handlers.clear()

    l1 = get_logger("test.common.logging.c")
    l2 = get_logger("test.common.logging.c")

    assert l1 is l2
    assert len(l1.handlers) == 1


def test_handler_writes_to_stdout() -> None:
    import sys

    logging.getLogger("test.common.logging.d").handlers.clear()
    logger = get_logger("test.common.logging.d")
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout
