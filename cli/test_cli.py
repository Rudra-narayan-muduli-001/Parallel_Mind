from cli.display import parse_comma_indices
from cli.run_config import RunConfig


class TestParseCommaIndices:
    def test_single_valid(self):
        assert parse_comma_indices("3", 5) == [2]

    def test_multiple_valid(self):
        assert parse_comma_indices("1,3,4", 5) == [0, 2, 3]

    def test_with_spaces(self):
        assert parse_comma_indices("1 , 3 , 4", 5) == [0, 2, 3]

    def test_out_of_range_ignored(self):
        assert parse_comma_indices("0,1,6", 5) == [0]
        assert parse_comma_indices("1,99", 5) == [0]

    def test_non_digit_ignored(self):
        assert parse_comma_indices("abc,1,def,3", 5) == [0, 2]

    def test_empty_string(self):
        assert parse_comma_indices("", 5) == []

    def test_all_valid(self):
        assert parse_comma_indices("1,2,3,4,5", 5) == [0, 1, 2, 3, 4]

    def test_single_at_boundary(self):
        assert parse_comma_indices("5", 5) == [4]
        assert parse_comma_indices("1", 1) == [0]


class TestRunConfig:
    def test_default_mode(self):
        cfg = RunConfig()
        assert cfg.mode == "default"
        assert cfg.effort == "low"
        assert cfg.selected_providers == []
        assert cfg.selected_targets == []

    def test_manual_mode(self):
        cfg = RunConfig(mode="manual", effort="high", selected_targets=[("groq", "llama-3.1-70b")])
        assert cfg.mode == "manual"
        assert cfg.effort == "high"
        assert cfg.selected_targets == [("groq", "llama-3.1-70b")]

    def test_selected_providers(self):
        cfg = RunConfig(mode="manual", selected_providers=["groq", "openai"])
        assert cfg.selected_providers == ["groq", "openai"]
