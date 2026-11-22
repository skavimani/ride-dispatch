import gc
import json
import os
import platform
import sys
import tracemalloc

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def save(name, data):
    os.makedirs(RESULTS, exist_ok=True)
    data = {"python": sys.version.split()[0], "machine": platform.machine(), "data": data}
    with open(os.path.join(RESULTS, f"{name}.json"), "w") as f:
        json.dump(data, f, indent=1, default=str)


def load(name):
    with open(os.path.join(RESULTS, f"{name}.json")) as f:
        return json.load(f)["data"]


def memory_of(build):
    """Bytes still allocated by the object that build() returns."""
    gc.collect()
    tracemalloc.start()
    obj = build()
    gc.collect()
    size, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del obj
    return size
