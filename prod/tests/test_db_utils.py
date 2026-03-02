"""Tests for shared.db.utils — JSON helpers, SQL builders, error detection."""

import pytest

from shared.db.utils import (
    serialize_json,
    deserialize_json,
    is_duplicate_key_error,
    build_update,
    truncate_error,
    MAX_ERROR_LOG_LENGTH,
)


class TestSerializeJson:
    def test_dict(self):
        assert serialize_json({"a": 1}) == '{"a": 1}'

    def test_list(self):
        assert serialize_json(["x", "y"]) == '["x", "y"]'

    def test_none_returns_none(self):
        assert serialize_json(None) is None

    def test_empty_dict_returns_none(self):
        assert serialize_json({}) is None

    def test_empty_list_returns_none(self):
        assert serialize_json([]) is None


class TestDeserializeJson:
    def test_valid_json_string(self):
        assert deserialize_json('{"a": 1}') == {"a": 1}

    def test_already_dict(self):
        d = {"a": 1}
        assert deserialize_json(d) is d

    def test_already_list(self):
        lst = [1, 2]
        assert deserialize_json(lst) is lst

    def test_none_returns_default(self):
        assert deserialize_json(None) is None
        assert deserialize_json(None, default=[]) == []

    def test_empty_string_returns_default(self):
        assert deserialize_json("") is None
        assert deserialize_json("", default={}) == {}

    def test_invalid_json_returns_default(self):
        assert deserialize_json("not json") is None
        assert deserialize_json("{broken", default="fallback") == "fallback"

    def test_json_list_string(self):
        assert deserialize_json('["a", "b"]') == ["a", "b"]


class TestIsDuplicateKeyError:
    def test_mysql_1062(self):
        exc = Exception("(1062, \"Duplicate entry 'abc' for key 'name'\")")
        assert is_duplicate_key_error(exc) is True

    def test_other_error(self):
        exc = Exception("Connection refused")
        assert is_duplicate_key_error(exc) is False

    def test_integrity_error_with_code(self):
        exc = Exception("IntegrityError: 1062 Duplicate entry")
        assert is_duplicate_key_error(exc) is True


class TestBuildUpdate:
    def test_single_field(self):
        result = build_update("users", "id", 42, name="Alice")
        assert result is not None
        sql, params = result
        assert "UPDATE users SET name = :name WHERE id = :id" == sql
        assert params == {"id": 42, "name": "Alice"}

    def test_multiple_fields(self):
        result = build_update("channels", "id", 1, name="ch1", enabled=1)
        assert result is not None
        sql, params = result
        assert "name = :name" in sql
        assert "enabled = :enabled" in sql
        assert params["name"] == "ch1"
        assert params["enabled"] == 1
        assert params["id"] == 1

    def test_none_fields_skipped(self):
        result = build_update("users", "id", 1, name=None, email="a@b.com")
        assert result is not None
        sql, params = result
        assert "name" not in sql
        assert "email = :email" in sql
        assert "name" not in params

    def test_all_none_returns_none(self):
        result = build_update("users", "id", 1, name=None, email=None)
        assert result is None

    def test_no_fields_returns_none(self):
        result = build_update("users", "id", 1)
        assert result is None


class TestTruncateError:
    def test_short_message(self):
        assert truncate_error("short") == "short"

    def test_none(self):
        assert truncate_error(None) is None

    def test_long_message_truncated(self):
        msg = "x" * 300
        result = truncate_error(msg)
        assert len(result) == MAX_ERROR_LOG_LENGTH

    def test_custom_length(self):
        msg = "hello world"
        assert truncate_error(msg, 5) == "hello"

    def test_exact_length_not_truncated(self):
        msg = "x" * MAX_ERROR_LOG_LENGTH
        assert truncate_error(msg) == msg
