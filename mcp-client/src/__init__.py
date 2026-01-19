"""
MCP Client Library for CloudWatch Logs
"""

from .mcp_client import MCPClient, MCPError, create_mcp_client

__all__ = ['MCPClient', 'MCPError', 'create_mcp_client']
__version__ = '0.1.0'
