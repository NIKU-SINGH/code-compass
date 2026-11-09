"""HTTP API over the code-compass engine.

A thin FastAPI adapter: routes parse input, call one ``compass_core.query`` function
and return its ``compass_core.contract`` result. No graph queries live here.
"""
