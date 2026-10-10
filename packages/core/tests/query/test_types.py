import json

from compass_core.query.types import CaveatCode, Language, Outcome, SymbolKind


def test_enums_serialize_as_strings():
    assert Outcome.NOT_FOUND == "not_found"
    assert SymbolKind.FUNCTION == "function"
    assert Language.PYTHON == "python"
    assert json.dumps({"o": Outcome.OK}) == '{"o": "ok"}'


def test_caveat_codes_present():
    assert CaveatCode.STALE_INDEX.name == "STALE_INDEX"
