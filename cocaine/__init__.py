# This is a namespace package
__import__('pkg_resources').declare_namespace(__name__)


from .server.worker import Worker

__all__ = ['Worker']