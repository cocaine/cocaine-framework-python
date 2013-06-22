from _callablewrappers import proxy_factory

__all__ = ["default"]


def default(func):
    return proxy_factory(func, None, None)
