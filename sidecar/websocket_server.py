"""
WebSocket Server - Bi-directional communication with Rust

Handles WebSocket connections from the Tauri application and
manages command/event exchange using JSON-RPC 2.0 protocol.
"""

import asyncio
import json
from typing import Optional, Dict, Any, Callable, Awaitable, cast
import websockets
from websockets.server import WebSocketServerProtocol # type: ignore
from websockets.exceptions import ConnectionClosed

from . import utils
from . import constants
from . import exceptions


# Type alias for command handlers
CommandHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

logger = utils.get_logger(__name__)


class WebSocketServer:
    """
    WebSocket server for bi-directional communication with Rust.
    
    Implements JSON-RPC 2.0 protocol for command/response exchange.
    Handlers can be registered for specific methods, and messages
    are routed to the appropriate handler.
    
    Example:
        >>> server = WebSocketServer(port=9001)
        >>> server.register_handler("chat.send", handle_chat)
        >>> await server.start()
    """
    
    def __init__(self, port: int, host: str = constants.DEFAULT_WEBSOCKET_HOST):
        """
        Initialize WebSocket server.
        
        Args:
            port: Port to listen on
            host: Host address to bind to (default: localhost)
        """
        self.port = port
        self.host = host
        self.connection: Optional[WebSocketServerProtocol] = None
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.command_handlers: Dict[str, CommandHandler] = {}
        self.pending_messages: list[Dict[str, Any]] = []
        
        logger.info(f"WebSocket server initialized on {host}:{port}")
    
    def register_handler(self, method: str, handler: Callable[..., Any]) -> None:
        """
        Register a command handler.
        
        Args:
            method: Command method name (e.g., "chat.send_message")
            handler: Async or sync function to handle the command
        
        Example:
            >>> async def handle_chat(params):
            ...     return {"status": "ok"}
            >>> server.register_handler("chat.send", handle_chat)
        """
        if not asyncio.iscoroutinefunction(handler):
            logger.warning(f"Handler for '{method}' is not async, wrapping it")
            # Wrap sync function in async
            async def async_wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
                result = handler(params)
                if asyncio.iscoroutine(result):
                    return cast(Dict[str, Any], await result)
                return cast(Dict[str, Any], result)
            self.command_handlers[method] = async_wrapper
        else:
            self.command_handlers[method] = handler
        
        logger.debug(f"Registered handler for method: {method}")
    
    async def start(self) -> None:
        """
        Start the WebSocket server.
        
        Starts listening for connections and handling messages.
        This method runs until the server is stopped.
        """
        logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")
        
        async with websockets.serve(
            self.handle_connection,
            self.host,
            self.port,
        ):
            logger.info(f"WebSocket server listening on ws://{self.host}:{self.port}")
            
            # Send any pending messages that were queued before server started
            if self.pending_messages and self.connection:
                logger.debug(f"Sending {len(self.pending_messages)} pending messages")
                for msg in self.pending_messages:
                    await self.send(msg)
                self.pending_messages.clear()
            
            # Run forever
            await asyncio.Future()
    
    async def handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle incoming WebSocket connection.
        
        Args:
            websocket: WebSocket connection instance
        """
        client_addr = websocket.remote_address
        logger.info(f"Client connected from {client_addr}")
        self.connection = websocket
        
        try:
            async for message in websocket:
                await self.handle_message(message)
        
        except ConnectionClosed as e:
            logger.info(f"Client disconnected: {e.code} - {e.reason}")
        
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        
        finally:
            self.connection = None
            logger.debug("Connection closed")
    
    async def handle_message(self, message: str) -> None:
        """
        Handle incoming message from Rust.
        
        Parses JSON-RPC message, validates it, routes to appropriate handler,
        and sends back response.
        
        Args:
            message: JSON-RPC message string
        """
        request_id: Optional[str] = None
        
        try:
            # Parse JSON
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {message[:100]}")
                raise exceptions.WebSocketMessageError(message, f"JSON parse error: {e}")
            
            # Validate JSON-RPC structure
            try:
                utils.validate_jsonrpc_message(data)
            except exceptions.JSONRPCError as e:
                logger.error(f"Invalid JSON-RPC message: {e.message}")
                raise
            
            # Extract message components
            request_id = utils.get_request_id(data)
            method = utils.get_method(data)
            params = utils.get_params(data)
            
            if not method:
                logger.error(f"Message missing method: {data}")
                return
            
            logger.debug(f"Received command: {method}")
            
            # Call handler if registered
            if method in self.command_handlers:
                try:
                    result = await self.command_handlers[method](params)
                    
                    # Send success response
                    response = utils.build_response(result, request_id=request_id)
                    await self.send(response)
                    
                    logger.debug(f"Command '{method}' executed successfully")
                
                except Exception as e:
                    logger.error(f"Handler error for '{method}': {e}", exc_info=True)
                    
                    # Send error response
                    error_response = utils.build_internal_error(
                        message=str(e),
                        details={
                            "method": method,
                            "error_type": type(e).__name__,
                        },
                        request_id=request_id,
                    )
                    await self.send(error_response)
            
            else:
                logger.warning(f"No handler registered for method: {method}")
                # Could send method not found error here
        
        except exceptions.WebSocketMessageError as e:
            logger.error(f"Message handling error: {e.message}")
        
        except exceptions.JSONRPCError as e:
            logger.error(f"JSON-RPC error: {e.message}")
       
        except Exception as e:
            logger.error(f"Unexpected error handling message: {e}", exc_info=True)
    
    async def send(self, data: Dict[str, Any]) -> None:
        """
        Send message to Rust.
        
        Args:
            data: Message data (will be JSON encoded)
        """
        if self.connection:
            try:
                message = json.dumps(data)
                await self.connection.send(message)
                logger.debug(f"Sent message: {data.get('method', 'response')}")
            except Exception as e:
                logger.error(f"Send error: {e}", exc_info=True)
        else:
            logger.warning("No active connection, cannot send message")
    
    def send_to_rust(self, data: Dict[str, Any]) -> None:
        """
        Send data to Rust (safe to call from sync or async context).
        
        This method can be called from synchronous code (e.g., plugins).
        It will queue the message to be sent when the event loop is available.
        
        Args:
            data: Dictionary to send as JSON-RPC message
        """
        # Try to create task if event loop is running
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.send(data))
        except RuntimeError:
            # No running loop yet - queue message to send when connected
            logger.debug(f"Queuing message (no event loop): {data.get('method', 'unknown')}")
            self.pending_messages.append(data)
    
    def get_registered_methods(self) -> list[str]:
        """
        Get list of all registered method names.
        
        Returns:
            List of method names
        """
        return list(self.command_handlers.keys())
    
    def is_connected(self) -> bool:
        """
        Check if a client is currently connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self.connection is not None
