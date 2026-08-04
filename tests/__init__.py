# Tests package
import asyncio
import sys

if sys.platform == "win32":
    import types

    sys.modules["fcntl"] = types.ModuleType("fcntl")
    sys.modules["resource"] = types.ModuleType("resource")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass
