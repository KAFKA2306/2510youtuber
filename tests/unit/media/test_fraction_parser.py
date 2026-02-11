import pytest
from app.services.media.fractions import FractionParser
@pytest.mark.unit
class TestFractionParser:
    def setup_method(self) -> None:
        self.parser = FractionParser()
    def test_parses_fraction_string(self) -> None:
        result = self.parser.parse("30000/1001")
        assert result.is_valid
        assert result.value == pytest.approx(29.97002997, rel=1e-6)
    def test_parses_decimal_string(self) -> None:
        result = self.parser.parse("24.0")
        assert result.is_valid
        assert result.value == pytest.approx(24.0)
    def test_handles_na_value(self) -> None:
        result = self.parser.parse("N/A")
        assert not result.is_valid
        assert result.value == 0.0
    def test_handles_empty_string(self) -> None:
        result = self.parser.parse("")
        assert not result.is_valid
        assert result.value == 0.0
    def test_handles_none(self) -> None:
        result = self.parser.parse(None)
        assert not result.is_valid
        assert result.value == 0.0
    def test_handles_zero_denominator(self) -> None:
        result = self.parser.parse("1/0")
        assert not result.is_valid
        assert result.value == 0.0
    def test_strips_whitespace(self) -> None:
        result = self.parser.parse("  60000 / 1001  ")
        assert result.is_valid
        assert result.value == pytest.approx(59.94005994, rel=1e-6)
