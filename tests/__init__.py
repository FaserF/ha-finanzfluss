# Tests package
import sys
import asyncio

if sys.platform == "win32":
    import types

    sys.modules["fcntl"] = types.ModuleType("fcntl")
    sys.modules["resource"] = types.ModuleType("resource")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass
