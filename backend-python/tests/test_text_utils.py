from app.utils.text_utils import parse_constraints


def test_parse_constraints_from_text() -> None:
    text = "利润率不低于15%，最低售价不低于99，最高售价不高于199"
    result = parse_constraints(text)
    assert str(result["min_profit_rate"]) == "0.15"
    assert str(result["min_price"]) == "99"
    assert str(result["max_price"]) == "199"

