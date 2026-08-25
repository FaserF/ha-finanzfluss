# Tests package
import asyncio
import contextlib
import sys

if sys.platform == "win32":
    import types

    sys.modules["fcntl"] = types.ModuleType("fcntl")
    sys.modules["resource"] = types.ModuleType("resource")
    with contextlib.suppress(AttributeError):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
