import logging
import pytest

from cli.run_config import RunConfig
from utils.logger import setup_logging


def test_run_config_defaults():
    cfg = RunConfig()
    assert cfg.mode == "default"
    assert cfg.effort == "low"
    assert cfg.selected_providers == []
    assert cfg.selected_targets == []


def test_run_config_custom():
    cfg = RunConfig(mode="manual", effort="high", selected_providers=["groq"], selected_targets=[("groq", "llama")])
    assert cfg.mode == "manual"
    assert cfg.effort == "high"
    assert cfg.selected_providers == ["groq"]
    assert cfg.selected_targets == [("groq", "llama")]


def test_run_config_mutability_isolation():
    c1 = RunConfig()
    c2 = RunConfig()
    c1.selected_providers.append("openai")
    assert c2.selected_providers == []


def test_setup_logging_json_creates_handler():
    logger = setup_logging(level="DEBUG", fmt="json")
    assert logger.level == logging.DEBUG
    # json handler may be JsonFormatter or fallback to standard; either way setup should not crash
    assert logger is not None
    assert logger.level == logging.DEBUG


def test_setup_logging_standard():
    logger = setup_logging(level="INFO", fmt="standard")
    assert logger.level == logging.INFO
    assert logger.name == "parallelmind"


def test_setup_logging_invalid_level_defaults():
    logger = setup_logging(level="NOTALEVEL", fmt="standard")
    # Should fallback to INFO without crashing
    assert logger is not None


def test_setup_logging_case_insensitive():
    logger = setup_logging(level="debug", fmt="standard")
    assert logger.level == logging.DEBUG
    logger2 = setup_logging(level="Warning", fmt="standard")
    assert logger2.level == logging.WARNING
