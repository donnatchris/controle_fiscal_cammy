from decimal import Decimal

import pytest

from shared.parse_money import parse_money


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("€299.00", Decimal("299.00")),
        ("299.00", Decimal("299.00")),
        ("€1,233.50", Decimal("1233.50")),
        ("€1_233.50", Decimal("1233.50")),
        ("€1*233.50", Decimal("1233.50")),
    ],
)
def test_parse_money(
    raw_value: str,
    expected: Decimal,
) -> None:
    assert parse_money(raw_value) == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "",
        "€abc",
        "€12.3",
    ],
)
def test_parse_money_refuse_montant_invalide(
    raw_value: str,
) -> None:
    with pytest.raises(ValueError):
        parse_money(raw_value)
