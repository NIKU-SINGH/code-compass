"""Public contract of the query engine: the types every adapter sends and receives.

Plain frozen dataclasses and enums with no database, I/O or adapter imports. The
query layer builds these values; the CLI, the MCP server and the HTTP server consume
them. Only ``serialize.py`` uses Pydantic, to turn them into JSON.
"""
