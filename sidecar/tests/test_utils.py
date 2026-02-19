"""
Tests for Utilities.
"""

import pytest
from sidecar import utils, exceptions


# JSON-RPC Tests
def test_build_request():
    req = utils.build_request("test", {"a": 1}, request_id="123")
    assert req == {"jsonrpc": "2.0", "method": "test", "params": {"a": 1}, "id": "123"}


def test_build_response():
    res = utils.build_response("success", request_id="123")
    assert res == {"jsonrpc": "2.0", "result": "success", "id": "123"}


def test_build_error():
    err = utils.build_error(100, "error", request_id="123")
    assert err == {
        "jsonrpc": "2.0",
        "error": {"code": 100, "message": "error"},
        "id": "123",
    }


def test_validate_jsonrpc_message_valid():
    # Valid Request
    utils.validate_jsonrpc_message({"jsonrpc": "2.0", "method": "test", "params": {}})

    # Valid Response
    utils.validate_jsonrpc_message({"jsonrpc": "2.0", "result": "ok", "id": "1"})


def test_validate_jsonrpc_message_invalid():
    # Missing version
    with pytest.raises(exceptions.JSONRPCError, match="Missing 'jsonrpc' field"):
        utils.validate_jsonrpc_message({"method": "test"})

    # Invalid method type
    with pytest.raises(exceptions.JSONRPCError, match="Method must be a string"):
        utils.validate_jsonrpc_message({"jsonrpc": "2.0", "method": 123})

    # Both result and error
    with pytest.raises(exceptions.JSONRPCError, match="Response cannot have both"):
        utils.validate_jsonrpc_message(
            {"jsonrpc": "2.0", "result": 1, "error": {"code": 1, "message": "e"}}
        )


# Path Tests
def test_validate_vault_path(tmp_path):
    # Valid
    assert utils.validate_vault_path(tmp_path) == tmp_path.resolve()

    # Non-existent
    with pytest.raises(exceptions.VaultNotFoundError):
        utils.validate_vault_path(tmp_path / "non_existent")

    # File not dir
    f = tmp_path / "test_file"
    f.touch()
    with pytest.raises(exceptions.InvalidPathError, match="Path is not a directory"):
        utils.validate_vault_path(f)


# ID Generation
def test_generate_id():
    id1 = utils.generate_id()
    id2 = utils.generate_id()
    assert id1 != id2
    assert "_" in id1

    id3 = utils.generate_id("prefix_")
    assert id3.startswith("prefix_")
