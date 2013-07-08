import ast
import re

from cocaine.exceptions import ServiceCallError, ServiceError
from cocaine.services import Service
from cocaine.futures.chain import Chain

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class Action(object):
    def __init__(self, node=None, **config):
        self.node = node
        self.config = config

    def execute(self):
        raise NotImplementedError()


class Info(Action):
    def execute(self):
        return self.node.info()


class Call(Action):
    def __init__(self, node, **config):
        super(Call, self).__init__(node, **config)
        command = config.get('command')
        if not command:
            raise ValueError('Please specify service name for getting API or full command to invoke')
        service, separator, methodWithArguments = command.partition('.')
        self.serviceName = service
        rx = re.compile(r'(.*?)\((.*)\)')
        match = rx.match(methodWithArguments)
        if match:
            self.methodName, self.args = match.groups()
        else:
            self.methodName = methodWithArguments

    def execute(self):
        return Chain([self.callService])

    def callService(self):
        service = self.getService()
        response = {
            'service': self.serviceName,
        }
        if not self.methodName:
            api = service._service_api
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
            service = Service(self.serviceName)
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