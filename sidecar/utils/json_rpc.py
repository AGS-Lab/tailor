"""
Tailor - JSON-RPC Utilities Module

Utilities for building and validating JSON-RPC 2.0 messages.
Provides consistent message formatting across the application.
"""

from typing import Dict, Any, Optional, Union
import time

from ..constants import (
    JSONRPC_VERSION,
    JSONRPC_PARSE_ERROR,
    JSONRPC_INVALID_REQUEST,
    JSONRPC_METHOD_NOT_FOUND,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_INTERNAL_ERROR,
)
from ..exceptions import JSONRPCError


def build_request(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a JSON-RPC 2.0 request message.
    
    Args:
        method: Method name to call
        params: Optional parameters dictionary
        request_id: Optional request ID. If None, generates a timestamp-based ID.
    
    Returns:
        JSON-RPC request dictionary
    
    Example:
        >>> request = build_request("chat.send_message", {"message": "Hello"})
        >>> # {"jsonrpc": "2.0", "method": "chat.send_message", "params": {...}, "id": "..."}
    """
    message: Dict[str, Any] = {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
    }
    
    if params is not None:
        message["params"] = params
    
    if request_id is None:
        request_id = f"req_{int(time.time() * 1000)}"
    
    message["id"] = request_id
    
    return message


def build_response(
    result: Any,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a JSON-RPC 2.0 success response message.
    
    Args:
        result: Result data to return
        request_id: Request ID from the original request
    
    Returns:
        JSON-RPC response dictionary
    
    Example:
        >>> response = build_response({"status": "success"}, request_id="123")
        >>> # {"jsonrpc": "2.0", "result": {...}, "id": "123"}
    """
    return {
        "jsonrpc": JSONRPC_VERSION,
        "result": result,
        "id": request_id,
    }


def build_error(
    code: int,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a JSON-RPC 2.0 error response message.
    
    Args:
        code: Error code (use constants like JSONRPC_INTERNAL_ERROR)
        message: Human-readable error message
        data: Optional additional error data
        request_id: Request ID from the original request
    
    Returns:
        JSON-RPC error response dictionary
    
    Example:
        >>> error = build_error(
        ...     JSONRPC_INTERNAL_ERROR,
        ...     "Plugin failed",
        ...     {"plugin": "example"},
        ...     request_id="123"
        ... )
    """
    error_obj = {
        "code": code,
        "message": message,
    }
    
    if data is not None:
        error_obj["data"] = data
    
    return {
        "jsonrpc": JSONRPC_VERSION,
        "error": error_obj,
        "id": request_id,
    }


def build_parse_error(request_id: Optional[str] = None) -> Dict[str, Any]:
    """Build a JSON parse error response."""
    return build_error(
        JSONRPC_PARSE_ERROR,
        "Parse error",
        data={"description": "Invalid JSON was received by the server"},
        request_id=request_id,
    )


def build_invalid_request_error(request_id: Optional[str] = None) -> Dict[str, Any]:
    """Build an invalid request error response."""
    return build_error(
        JSONRPC_INVALID_REQUEST,
        "Invalid Request",
        data={"description": "The JSON sent is not a valid Request object"},
        request_id=request_id,
    )


def build_method_not_found_error(
    method: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a method not found error response."""
    return build_error(
        JSONRPC_METHOD_NOT_FOUND,
        f"Method not found: {method}",
        data={"method": method},
        request_id=request_id,
    )


def build_invalid_params_error(
    reason: str,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an invalid params error response."""
    return build_error(
        JSONRPC_INVALID_PARAMS,
        "Invalid params",
        data={"reason": reason},
        request_id=request_id,
    )


def build_internal_error(
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an internal error response."""
    return build_error(
        JSONRPC_INTERNAL_ERROR,
        message,
        data=details,
        request_id=request_id,
    )


def validate_jsonrpc_message(message: Dict[str, Any]) -> None:
    """
    Validate that a message conforms to JSON-RPC 2.0 spec.
    
    Args:
        message: Message dictionary to validate
    
    Raises:
        JSONRPCError: If message is invalid
    
    Example:
        >>> try:
        ...     validate_jsonrpc_message(msg)
        ... except JSONRPCError as e:
        ...     logger.error(f"Invalid message: {e}")
    """
    # Check jsonrpc version
    if "jsonrpc" not in message:
        raise JSONRPCError("Missing 'jsonrpc' field", JSONRPC_INVALID_REQUEST)
    
    if message["jsonrpc"] != JSONRPC_VERSION:
        raise JSONRPCError(
            f"Invalid JSON-RPC version: {message['jsonrpc']}",
            JSONRPC_INVALID_REQUEST
        )
    
    # Check if it's a request or response
    if "method" in message:
        # Request validation
        if not isinstance(message["method"], str):
            raise JSONRPCError("Method must be a string", JSONRPC_INVALID_REQUEST)
        
        if "params" in message and not isinstance(message["params"], (dict, list)):
            raise JSONRPCError("Params must be object or array", JSONRPC_INVALID_PARAMS)
    
    elif "result" in message or "error" in message:
        # Response validation
        if "result" in message and "error" in message:
            raise JSONRPCError(
                "Response cannot have both 'result' and 'error'",
                JSONRPC_INVALID_REQUEST
            )
        
        if "error" in message:
            error = message["error"]
            if not isinstance(error, dict):
                raise JSONRPCError("Error must be an object", JSONRPC_INVALID_REQUEST)
            
            if "code" not in error or "message" not in error:
                raise JSONRPCError(
                    "Error must have 'code' and 'message'",
                    JSONRPC_INVALID_REQUEST
                )
    
    else:
        raise JSONRPCError(
            "Message must be request or response",
            JSONRPC_INVALID_REQUEST
        )


def is_request(message: Dict[str, Any]) -> bool:
    """
    Check if a message is a JSON-RPC request (has method and id).
    
    Args:
        message: Message dictionary
    
    Returns:
        True if message is a request, False otherwise
    """
    return "method" in message and "id" in message


def is_response(message: Dict[str, Any]) -> bool:
    """
    Check if a message is a JSON-RPC response.
    
    Args:
        message: Message dictionary
    
    Returns:
        True if message is a response, False otherwise
    """
    return "result" in message or "error" in message


def is_notification(message: Dict[str, Any]) -> bool:
    """
    Check if a message is a JSON-RPC notification (request without ID).
    
    Args:
        message: Message dictionary
    
    Returns:
        True if message is a notification, False otherwise
    """
    return "method" in message and "id" not in message


def get_request_id(message: Dict[str, Any]) -> Optional[str]:
    """
    Extract request ID from a JSON-RPC message.
    
    Args:
        message: Message dictionary
    
    Returns:
        Request ID if present, None otherwise
    """
    return message.get("id")


def get_method(message: Dict[str, Any]) -> Optional[str]:
    """
    Extract method name from a JSON-RPC request.
    
    Args:
        message: Message dictionary
    
    Returns:
        Method name if present, None otherwise
    """
    return message.get("method")


def get_params(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract params from a JSON-RPC request.
    
    Args:
        message: Message dictionary
    
    Returns:
        Parameters dictionary, empty dict if no params
    """
    params = message.get("params", {})
    
    # Convert list params to dict (some clients might send arrays)
    if isinstance(params, list):
        return {"args": params}
    
    return params if isinstance(params, dict) else {}
