from compass_core.errors import (
    CompassError,
    ErrorCode,
    IndexIncompatibleError,
    IndexNotFoundError,
    InvalidArgumentError,
    ParseError,
    QueryError,
    UnsupportedLanguageError,
)


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


def test_every_query_error_declares_a_unique_code():
    codes = [cls.code for cls in QueryError.__subclasses__()]
    assert len(codes) == len(set(codes))
    assert ErrorCode.INDEX_NOT_FOUND in codes and ErrorCode.INDEX_INCOMPATIBLE in codes


def test_invalid_argument_carries_context():
    err = InvalidArgumentError(argument="depth", reason="must be between 1 and 10")
    assert err.code is ErrorCode.INVALID_ARGUMENT and err.argument == "depth"


def test_index_errors_are_query_errors():
    assert issubclass(IndexNotFoundError, QueryError)
    assert issubclass(IndexIncompatibleError, QueryError)
