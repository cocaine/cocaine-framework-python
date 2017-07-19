'''Secure service adaptor.

Provides method for Service adaptor construction, capable to wrap Cocaine
service and inject security token into the header of service request.

Note: mostly copy-pasted from cocaine-tools `SecureService` implementation.
'''
import time

from tornado import gen

from .service import Service
from ..exceptions import CocaineError


class SecureServiceError(CocaineError):
    pass


class Promiscuous(object):
    '''Null token fetch interface implementation.

    Used for fallback in case of unsupported (not set) secure module type
    provided by user, access errors due empty token will be propagated
    to caller code.
    '''
    @gen.coroutine
    def fetch_token(self):
        raise gen.Return('')


class TVM(object):
    '''Tokens fetch interface implementation.

    Provides public `fetch_token` method, which should be common
    among various token backends types.

    Attributes:
        TYPE (str): String representation of token fetcher type,
            will be included in secure header.
    '''
    # Can be taken from class name in case of TVM, but could be inconvenient
    # in less general name formatting rules.
    TYPE = 'TVM'

    def __init__(self, client_id, client_secret, name='tvm'):
        '''TVM

        Args:
            client_id (int): Integer client identificator.
            client_secret (str): Client secret.
            name (str): TVM service name, defaults to 'tvm'.
        '''
        self._client_id = client_id
        self._client_secret = client_secret

        self._tvm = Service(name)

    @gen.coroutine
    def fetch_token(self):
        '''Gains token from secure backend service.
        Returns:
            str: token formatted for cocaine protocol header.
        '''
        grant_type = 'client_credentials'

        channel = yield self._tvm.ticket_full(
            self._client_id, self._client_secret, grant_type, {})
        ticket = yield channel.rx.get()

        raise gen.Return(self._make_token(ticket))

    def _make_token(self, ticket):
        return '{} {}'.format(self.TYPE, ticket)


class SecureServiceAdaptor(object):
    '''Wrapper for injecting service method with secure token.
    '''
    def __init__(self, wrapped, secure, tok_update_sec=None):
        '''
        Args:
            wrapped (cocaine.Service): Cocaine service.
            secure: Tokens provider with `fetch_token` implementation.
        '''
        self._wrapped = wrapped
        self._secure = secure

        self._to_expire = None
        self._tok_update_sec = tok_update_sec

        if tok_update_sec:
            self._to_expire = time.time() + tok_update_sec

        self._token = None

    @gen.coroutine
    def connect(self, traceid=None):
        yield self._wrapped.connect(traceid)

    def disconnect(self):
        return self._wrapped.disconnect()

    @gen.coroutine
    def _get_token(self):
        try:
            # TODO: Seems too many branches with common ending.
            if self._to_expire:
                if time.time() > self._to_expire:
                    # tok_update_sec should be set in __init__ when
                    # self._to_expire is valid
                    self._token = yield self._secure.fetch_token()
                    self._to_expire = time.time() + self._tok_update_sec
                elif not self._token:  # init state
                    self._token = yield self._secure.fetch_token()
            else:
                self._token = yield self._secure.fetch_token()
        except Exception as err:
            raise SecureServiceError(
                'failed to fetch secure token: {}'.format(err))

        raise gen.Return(self._token)

    def __getattr__(self, name):
        @gen.coroutine
        def wrapper(*args, **kwargs):
            kwargs['authorization'] = yield self._get_token()
            raise gen.Return(
                (yield getattr(self._wrapped, name)(*args, **kwargs))
            )

        return wrapper


class SecureServiceFabric(object):

    @staticmethod
    def make_secure_adaptor(
            service, mod, client_id, client_secret, tok_update_sec=None):
        '''
        Args:
            service (cocaine.Service): Service to wrap in.
            mod (str): Name (type) of token refresh backend.
            client_id (int): Client identificator.
            client_secret (str): Client secret.
            tok_update_sec (int, optional): Token update interval in seconds.
        '''
        if mod == 'TVM':
            return SecureServiceAdaptor(
                service, TVM(client_id, client_secret), tok_update_sec)

        return SecureServiceAdaptor(service, Promiscuous(), tok_update_sec)
