import json
import os
import time

CACHE_DIR = os.path.expanduser("~/.dore-and-rose/cache")


def _ensure_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def save_cache(key, data):
    _ensure_dir()
    path = os.path.join(CACHE_DIR, f"{key}.json")
    with open(path, "w") as f:
        json.dump({"saved_at": time.time(), "data": data}, f)


def load_cache(key):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def is_cache_stale(key, ttl_minutes=5):
    cached = load_cache(key)
    if not cached:
        return True
    age = time.time() - cached.get("saved_at", 0)
    return age > ttl_minutes * 60
