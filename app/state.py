import pickle

from redislite import Redis


class AppRedis(Redis):
    """Minimal class that wraps some Redis commands to store values
    serialized in pickle format"""
    def hset(self, name, key=None, value=None, mapping=None):
        value = pickle.dumps(value)
        return super().hset(name, key, value, mapping)

    def hget(self, name, key):
        value = super().hget(name, key)
        return pickle.loads(value) if value is not None else None

    def hvals(self, name):
        values = super().hvals(name)
        return [pickle.loads(v) for v in values] if values else []
