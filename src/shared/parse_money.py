import re


from decimal import Decimal


MONEY_PATTERN = r"^€?-?(?:\d{1,3}(?:,\d{3})*|\d+)\.\d{2}$"


def parse_money(value: str) -> Decimal:
	"""Parse la valeur monétaire et retourne un Decimal.

	Formats acceptes: "€1,234.56", "€1234.56", "€1_234.56", "€1*234.56"
	"""
	if not value:
		raise ValueError("Montant vide")
	
	cleaned_value = (
		value
		.strip()
		.replace("_", "")
		.replace("*", "")
	)

	if not re.fullmatch(MONEY_PATTERN, cleaned_value):
		raise ValueError(f"Montant invalide : {cleaned_value!r}")
	normalized = (
		cleaned_value
		.removeprefix("€")
		.replace(",", "")
	)

	return Decimal(normalized)
