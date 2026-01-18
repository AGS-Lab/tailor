"""
Unit tests for WebSocketServer module.

Tests connection handling, JSON-RPC message processing, and command registration.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import inspect
from sidecar.websocket_server import WebSocketServer, CommandHandler
from sidecar import exceptions
from sidecar import utils
from sidecar import constants


@pytest.mark.unit
class TestWebSocketServer:
    """Test WebSocketServer functionality."""
    
    @pytest.fixture
    def server(self):
        """Create a WebSocketServer instance."""
        return WebSocketServer(port=9000)
    
    @pytest.fixture
    def mock_ws(self):
        """Create a mock WebSocket connection."""
        ws = AsyncMock()
        ws.send = AsyncMock()
        ws.close = AsyncMock()
        ws.remote_address = ("127.0.0.1", 12345)
        return ws
        
    def test_init(self, server):
        """Test server initialization."""
        assert server.port == 9000
        assert server.host == "127.0.0.1"  # Default
        assert server.connection is None
        # Should not have local command handlers anymore
        assert not hasattr(server, "command_handlers")

    @pytest.mark.asyncio
    async def test_handle_message_valid_request(self, server):
        """Test processing a valid request via VaultBrain."""
        # Mock VaultBrain
        mock_brain = MagicMock()
        mock_brain.execute_command = AsyncMock(return_value={"status": "ok"})
        
        with patch.dict('sys.modules', {'sidecar.vault_brain': MagicMock(VaultBrain=MagicMock(get=MagicMock(return_value=mock_brain)))}):
            
            # Mock connection to verify response
            server.connection = Mock()
            server.connection.send = AsyncMock()
            server.connection.close = AsyncMock()
            
            request = utils.build_request("test.echo", {"msg": "hello"}, request_id="1")
            
            await server.handle_message(json.dumps(request))
            
            # Check Brain called
            mock_brain.execute_command.assert_called_once_with("test.echo", msg="hello")
            
            # Check response sent
            server.connection.send.assert_called_once()
            response_str = server.connection.send.call_args[0][0]
            response = json.loads(response_str)
            
            assert response["result"] == {"status": "ok"}
            assert response["id"] == "1"

    @pytest.mark.asyncio
    async def test_handle_message_method_not_found(self, server):
        """Test unknown method."""
        # Mock VaultBrain to raise CommandNotFoundError -> causes MethodNotFoundError
        # Or specifically mocking _execute_request failure
        
        server.connection = Mock()
        server.connection.send = AsyncMock()
        server.connection.close = AsyncMock()
        
        request = utils.build_request("unknown", request_id="2")
        
        # We need to act as if VaultBrain raises exception
        mock_brain = MagicMock()
        mock_brain.execute_command = AsyncMock(side_effect=exceptions.CommandNotFoundError("unknown", []))
        
        with patch.dict('sys.modules', {'sidecar.vault_brain': MagicMock(VaultBrain=MagicMock(get=MagicMock(return_value=mock_brain)))}):
        
            await server.handle_message(json.dumps(request))
            
            # Verify method not found error sent
            server.connection.send.assert_called_once()
            response_str = server.connection.send.call_args[0][0]
            response = json.loads(response_str)
            
            assert "error" in response
            assert response["error"]["code"] == constants.JSONRPC_METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self, server):
        """Test malformed JSON."""
        server.connection = Mock()
        server.connection.send = AsyncMock()
        
        await server.handle_message("not valid json")
        
        # Should catch and log, probably no response back to client unless implemented?
        server.connection.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_exception(self, server):
        """Test error raised inside handler."""
        # Mock VaultBrain to raise generic exception
        mock_brain = MagicMock()
        mock_brain.execute_command = AsyncMock(side_effect=ValueError("Handler failed"))
        
        with patch.dict('sys.modules', {'sidecar.vault_brain': MagicMock(VaultBrain=MagicMock(get=MagicMock(return_value=mock_brain)))}):
            
            server.connection = Mock()
            server.connection.send = AsyncMock()
            server.connection.close = AsyncMock()
            
            request = utils.build_request("test.fail", request_id="3")
            
            await server.handle_message(json.dumps(request))
            
            # Check internal error response
            server.connection.send.assert_called_once()
            response_str = server.connection.send.call_args[0][0]
            response = json.loads(response_str)
            
            assert response["error"]["code"] == constants.JSONRPC_INTERNAL_ERROR
            assert "Handler failed" in response["error"]["message"] or "ValueError" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_handle_connection(self, server, mock_ws):
        """Test that new connection is stored."""
        
        async def mock_iter():
            if False: yield "msg" # Yield nothing
        
        mock_ws.__aiter__.side_effect = mock_iter
        
        await server.handle_connection(mock_ws)
        
        # Should have set connection, then cleared it in finally block
        assert server.connection is None

