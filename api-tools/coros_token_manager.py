#!/usr/bin/env python3
"""Retired: COROS authentication now belongs to the connected MCP server."""
import sys


def get_valid_token(*args, **kwargs):
    raise RuntimeError("COROS Token login retired. Use COROS MCP; see README_MCP.md")


if __name__ == "__main__":
    sys.exit("COROS Token login retired. No credentials were read or changed. See README_MCP.md")
