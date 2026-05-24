"""Entry point for running the Nintendo MCP server as a module.

This file ensures the server is always imported as 'nintendo_mcp.server'
(never as '__main__'), so tool registrations from all submodules land on
the same FastMCP instance that gets served.

Usage:
    python -m nintendo_mcp.server   # via server.py if __name__ == '__main__'
    python -m nintendo_mcp          # via this file
"""

from nintendo_mcp.server import main

main()
