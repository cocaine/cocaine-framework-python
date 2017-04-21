from __future__ import unicode_literals

import unittest
from functools import partial
from unittest import skip

from mock import Mock
from tornado.ioloop import IOLoop

from cocaine.detail.channel import Tx
from cocaine.detail.headers import CocaineHeaders
from cocaine.detail.trace import Trace, TraceAdapter


class BaseTestCase(unittest.TestCase):
    tx_tree = {0: [b'dummy', None]}


class TestTxNoneInitialTraceId(BaseTestCase):
    def setUp(self):
        self.service_name = 'dummy_service'
        self.tx = Tx(self.tx_tree, Mock(), 1, CocaineHeaders(), self.service_name)
        self.initial_log = self.tx.log
        assert not isinstance(self.initial_log, TraceAdapter)

    def test_set_not_none_trace(self):
        new_trace_id = 100
        new_trace = Trace(new_trace_id, 2, 1)
        IOLoop.current().run_sync(partial(self.tx.dummy, trace=new_trace))
        # Set new trace_id, set new logger adapter
        assert self.tx.trace_id == new_trace_id
        assert self.tx.log.extra == {'trace_id': hex(new_trace_id)[2:]}

    def test_not_set_trace(self):
        IOLoop.current().run_sync(self.tx.dummy)
        # Keep trace_id None, keep general logging
        assert self.tx.trace_id is None
        assert not isinstance(self.tx.log, TraceAdapter)


class TestTxInitialTraceId(BaseTestCase):
    def setUp(self):
        self.service_name = 'dummy_service'
        self.initial_trace_id = 300  # greater than 256 to not use cached ints
        self.tx = Tx(self.tx_tree, Mock(), 1, CocaineHeaders(), self.service_name,
                     trace_id=self.initial_trace_id)
        self.initial_log = self.tx.log

    def test_set_not_none_trace_equal_trace_id(self):
        new_trace = Trace(300, 20, 10)

        IOLoop.current().run_sync(partial(self.tx.dummy, trace=new_trace))
        # Keep old trace_id, keep old logger
        assert self.tx.trace_id is not new_trace.traceid
        assert self.tx.log is self.initial_log

    def test_set_trace_with_not_equal_trace_id(self):
        new_trace_id = 100
        new_trace = Trace(new_trace_id, 20, 10)

        IOLoop.current().run_sync(partial(self.tx.dummy, trace=new_trace))
        # Set new trace_id and new logger
        assert self.tx.trace_id == new_trace_id
        assert self.tx.log.extra == {'trace_id': hex(new_trace_id)[2:]}

    def test_not_set_trace(self):
        IOLoop.current().run_sync(self.tx.dummy)

        # Keep old trace_id, keep old logger
        assert self.initial_trace_id is self.tx.trace_id
        assert self.tx.log is self.initial_log
