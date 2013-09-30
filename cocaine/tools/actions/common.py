import ast
import re

from cocaine.exceptions import ServiceError
from cocaine.futures import chain
from cocaine.services import Service
from cocaine.tools.error import ServiceCallError

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Node(object):
    def __init__(self, node=None):
        self.node = node

    def execute(self):
        raise NotImplementedError()


class NodeInfo(Node):
    def __init__(self, node, locator):
        super(NodeInfo, self).__init__(node)
        self.locator = locator

    @chain.source
    def execute(self):
        appNames = yield self.node.list()
        appInfoList = {}
        for appName in appNames:
            info = ''
            try:
                app = Service(appName, blockingConnect=False)
                yield app.connectThroughLocator(self.locator)
                info = yield app.info()
            except Exception as err:
                info = str(err)
            finally:
                appInfoList[appName] = info
        result = {
            'apps': appInfoList
        }
        yield result


class Call(object):
    def __init__(self, command, host='localhost', port=10053):
        if not command:
            raise ValueError('Please specify service name for getting API or full command to invoke')
        self.host = host
        self.port = port
        self.serviceName, separator, methodWithArguments = command.partition('.')
        rx = re.compile(r'(.*?)\((.*)\)')
        match = rx.match(methodWithArguments)
        if match:
            self.methodName, self.args = match.groups()
        else:
            self.methodName = methodWithArguments

    @chain.source
    def execute(self):
        service = self.getService()
        response = {
            'service': self.serviceName,
        }
        if not self.methodName:
            api = service.api
            response['request'] = 'api'
            response['response'] = api
        else:
            method = self.getMethod(service)
            args = self.parseArguments()
            result = yield method(*args)
            response['request'] = 'invoke'
            response['response'] = result
        yield response

    def getService(self):
        try:
            service = Service(self.serviceName, host=self.host, port=self.port)
            return service
        except Exception as err:
            raise ServiceCallError(self.serviceName, err)

    def getMethod(self, service):
        try:
            method = service.__getattribute__(self.methodName)
            return method
        except AttributeError:
            raise ServiceError(self.serviceName, 'method "{0}" is not found'.format(self.methodName), 1)

    def parseArguments(self):
        if not self.args:
            return ()

        try:
            args = ast.literal_eval(self.args)
            if not isinstance(args, tuple):
                args = (args,)
            return args
        except (SyntaxError, ValueError) as err:
            raise ServiceCallError(self.serviceName, err)
        except Exception as err:
            print(err, type(err))
