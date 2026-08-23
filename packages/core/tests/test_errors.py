from compass_core.errors import CompassError, ParseError, UnsupportedLanguageError


def test_compass_error_carries_context():
    err = ParseError("bad syntax", file_path="a.py", language="python", phase_name="parse")
    assert err.file_path == "a.py"
    assert err.language == "python"
    assert err.phase_name == "parse"
    assert str(err) == "bad syntax"


def test_subclasses_are_compass_error():
    assert issubclass(ParseError, CompassError)
    assert issubclass(UnsupportedLanguageError, CompassError)


def test_context_defaults_to_none():
    err = CompassError("generic failure")
    assert err.file_path is None
    assert err.language is None
    assert err.phase_name is None
