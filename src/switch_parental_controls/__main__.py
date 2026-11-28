"""Entry point for running the Nintendo CLI as a module.

Usage:
    python -m switch_parental_controls           # show CLI help
    python -m switch_parental_controls mcp       # start the MCP server
    python -m switch_parental_controls login     # interactive login
    python -m switch_parental_controls --help    # list all commands
"""

from switch_parental_controls.cli import cli

cli()
