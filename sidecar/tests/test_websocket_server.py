"""
Unit tests for WebSocketServer module.

Tests connection handling, JSON-RPC message processing, and command registration.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
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
        assert server.host == "localhost"  # Default
        assert server.connection is None
        assert server.command_handlers == {}

    def test_register_handler_async(self, server):
        """Test registering an async handler."""
        async def handler(params): return {}
        server.register_handler("test.method", handler)
        assert "test.method" in server.command_handlers
        assert server.command_handlers["test.method"] == handler

    def test_register_handler_sync(self, server):
        """Test registering a sync handler (wrapper)."""
        def handler(params): return {}
        server.register_handler("test.method", handler)
        assert "test.method" in server.command_handlers
        # Should be wrapped in async
        assert asyncio.iscoroutinefunction(server.command_handlers["test.method"])

    @pytest.mark.asyncio
    async def test_send_to_rust_connected(self, server, mock_ws):
        """Test sending message when connected."""
        server.connection = mock_ws
        # Use build_request
        message = utils.build_request("test")
        
        # Testing the async send() method directly is more reliable for unit tests
        await server.send(message)
        
        mock_ws.send.assert_called_once()
        sent_json = mock_ws.send.call_args[0][0]
        assert json.loads(sent_json) == message

    @pytest.mark.asyncio
    async def test_send_to_rust_no_loop_queues(self, server):
        """Test sending message when no loop (queues message)."""
        message = utils.build_request("test")
        
        # Mock get_running_loop to raise RuntimeError (simulate no loop)
        with patch("asyncio.get_running_loop", side_effect=RuntimeError):
            server.send_to_rust(message)
            
        assert message in server.pending_messages

    @pytest.mark.asyncio
    async def test_handle_message_valid_request(self, server):
        """Test processing a valid request."""
        # Register a handler
        handler = AsyncMock(return_value={"status": "ok"})
        server.register_handler("test.echo", handler)
        
        # Mock connection to verify response
        server.connection = Mock()
        server.connection.send = AsyncMock()
        
        request = utils.build_request("test.echo", {"msg": "hello"}, request_id="1")
        
        await server.handle_message(json.dumps(request))
        
        # Check handler called
        handler.assert_called_once_with({"msg": "hello"})
        
        # Check response sent
        server.connection.send.assert_called_once()
        response_str = server.connection.send.call_args[0][0]
        response = json.loads(response_str)
        
        assert response["result"] == {"status": "ok"}
        assert response["id"] == "1"

    @pytest.mark.asyncio
    async def test_handle_message_method_not_found(self, server):
        """Test unknown method."""
        server.connection = Mock()
        server.connection.send = AsyncMock()
        
        request = utils.build_request("unknown", request_id="2")
        
        # Implementation logs warning but doesn't strictly require sending error 
        
        await server.handle_message(json.dumps(request))
        
        # Verify NO response sent (based on current implementation)
        server.connection.send.assert_not_called()

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
        # Handler raises generic exception
        handler = AsyncMock(side_effect=ValueError("Handler failed"))
        server.register_handler("test.fail", handler)
        
        server.connection = Mock()
        server.connection.send = AsyncMock()
        
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

