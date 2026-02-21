import pytest

from app.common.namespaces import (
    DEFAULT_NAMESPACE,
    is_valid_namespace,
    merge_namespace_filters,
    parse_namespaces,
    validate_namespace,
)


def test_validate_namespace_defaults_to_default_when_omitted():
    assert validate_namespace(None) == DEFAULT_NAMESPACE
    assert validate_namespace("   ") == DEFAULT_NAMESPACE


def test_validate_namespace_accepts_valid_values():
    assert validate_namespace("abc") == "abc"
    assert validate_namespace("team_1.prod-a") == "team_1.prod-a"
    assert validate_namespace("a" * 64) == "a" * 64
    assert is_valid_namespace("a-b.c_d9")


def test_validate_namespace_rejects_invalid_values():
    with pytest.raises(ValueError):
        validate_namespace("NameWithUppercase", default_to_default=False)
    with pytest.raises(ValueError):
        validate_namespace("bad space", default_to_default=False)
    with pytest.raises(ValueError):
        validate_namespace("a" * 65, default_to_default=False)
    with pytest.raises(ValueError):
        validate_namespace("", default_to_default=False)


def test_parse_namespaces_supports_repeated_and_comma_separated_input():
    parsed = parse_namespaces(["alpha,beta", "beta", "gamma", "  alpha  "])
    assert parsed == ["alpha", "beta", "gamma"]


def test_merge_namespace_filters_none_and_single_namespace():
    assert merge_namespace_filters(None, None) is None
    assert merge_namespace_filters({"doc_id": "d1"}, None) == {"doc_id": "d1"}
    assert merge_namespace_filters(None, ["alpha"]) == {"namespace": "alpha"}


def test_merge_namespace_filters_multi_namespace_with_existing_filters():
    merged = merge_namespace_filters({"doc_id": "d1"}, ["alpha,beta"])
    assert merged == {
        "$and": [
            {"doc_id": "d1"},
            {"$or": [{"namespace": "alpha"}, {"namespace": "beta"}]},
        ]
    }
