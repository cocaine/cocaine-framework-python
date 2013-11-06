import logging
import os
import unittest
import sys

from tornado.testing import AsyncTestCase

from cocaine import concurrent
from cocaine.concurrent import Deferred, return_
from cocaine.concurrent.util import All, AllError
from cocaine.testing import trigger_check, DeferredMock


__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)
h = logging.StreamHandler(stream=sys.stdout)
log.addHandler(h)
log.setLevel(logging.DEBUG)
log.propagate = False


class DeferredTestCase(unittest.TestCase):
    def test_Class(self):
        Deferred()

    def test_CanStoreCallbacks(self):
        triggered = [False]
        actual = [None]

        def check(r):
            actual[0] = r.get()
            triggered[0] = True

        d = Deferred()
        d.add_callback(check)
        d.trigger('Test')

        self.assertTrue(triggered[0])
        self.assertEqual('Test', actual[0])

    def test_RaisesErrorOnErrorTrigger(self):
        triggered = [False]

        def check(r):
            self.assertRaises(ValueError, r.get)
            triggered[0] = True

        d = Deferred()
        d.add_callback(check)
        d.error(ValueError('Test'))

        self.assertTrue(triggered[0])

    def test_DoNotLoseChunkWhenCallbackIsNotSetYet(self):
        triggered = [False]
        actual = [None]

        d = Deferred()
        d.trigger('Test')

        def check(r):
            triggered[0] = True
            actual[0] = r.get()

        d.add_callback(check)

        self.assertTrue(triggered[0])
        self.assertEqual('Test', actual[0])


class EngineTestCase(AsyncTestCase):
    os.environ.setdefault('ASYNC_TEST_TIMEOUT', '0.5')

    def test_YieldDeferredWithSingleResult(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d = DeferredMock([1], io_loop=self.io_loop)
                result = yield d
                self.assertEqual(1, result)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldDeferredWithTwoResults(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d = DeferredMock([1, 2], io_loop=self.io_loop)
                r1 = yield d
                r2 = yield d
                self.assertEqual(1, r1)
                self.assertEqual(2, r2)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldDeferredWithMultipleResults(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d = DeferredMock([1, 2, 3, 4, 5], io_loop=self.io_loop)
                r1 = yield d
                r2 = yield d
                r3 = yield d
                r4 = yield d
                r5 = yield d
                self.assertEqual(1, r1)
                self.assertEqual(2, r2)
                self.assertEqual(3, r3)
                self.assertEqual(4, r4)
                self.assertEqual(5, r5)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldTwoDeferredWithSingleResultsSequentially(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1], io_loop=self.io_loop)
                r1 = yield d1
                d2 = DeferredMock([2], io_loop=self.io_loop)
                r2 = yield d2
                self.assertEqual(1, r1)
                self.assertEqual(2, r2)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldTwoDeferredWithSingleResultsParallel(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1], io_loop=self.io_loop)
                d2 = DeferredMock([2], io_loop=self.io_loop)
                r1 = yield d1
                r2 = yield d2
                self.assertEqual(1, r1)
                self.assertEqual(2, r2)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldTwoDeferredWithSingleResultsParallelReverse(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1], io_loop=self.io_loop)
                d2 = DeferredMock([2], io_loop=self.io_loop)
                r2 = yield d2
                r1 = yield d1
                self.assertEqual(1, r1)
                self.assertEqual(2, r2)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldTwoDeferredWithMultipleResultsParallel(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1, 2, 3, 4], io_loop=self.io_loop)
                d2 = DeferredMock(['a', 'b', 'c', 'd'], io_loop=self.io_loop)
                d1r1 = yield d1
                d1r2 = yield d1
                d1r3 = yield d1
                d1r4 = yield d1
                d2r1 = yield d2
                d2r2 = yield d2
                d2r3 = yield d2
                d2r4 = yield d2
                self.assertEqual(1, d1r1)
                self.assertEqual(2, d1r2)
                self.assertEqual(3, d1r3)
                self.assertEqual(4, d1r4)
                self.assertEqual('a', d2r1)
                self.assertEqual('b', d2r2)
                self.assertEqual('c', d2r3)
                self.assertEqual('d', d2r4)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldTwoDeferredWithMultipleResultsParallelTinyMixed(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1, 2, 3, 4], io_loop=self.io_loop)
                d2 = DeferredMock(['a', 'b', 'c', 'd'], io_loop=self.io_loop)
                d1r1 = yield d1
                d2r1 = yield d2
                d1r2 = yield d1
                d1r3 = yield d1
                d1r4 = yield d1
                d2r2 = yield d2
                d2r3 = yield d2
                d2r4 = yield d2
                self.assertEqual(1, d1r1)
                self.assertEqual(2, d1r2)
                self.assertEqual(3, d1r3)
                self.assertEqual(4, d1r4)
                self.assertEqual('a', d2r1)
                self.assertEqual('b', d2r2)
                self.assertEqual('c', d2r3)
                self.assertEqual('d', d2r4)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldTwoDeferredWithMultipleResultsParallelPairMixed(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1, 2, 3, 4], io_loop=self.io_loop)
                d2 = DeferredMock(['a', 'b', 'c', 'd'], io_loop=self.io_loop)
                d1r1 = yield d1
                d2r1 = yield d2
                d1r2 = yield d1
                d2r2 = yield d2
                d1r3 = yield d1
                d2r3 = yield d2
                d1r4 = yield d1
                d2r4 = yield d2
                self.assertEqual(1, d1r1)
                self.assertEqual(2, d1r2)
                self.assertEqual(3, d1r3)
                self.assertEqual(4, d1r4)
                self.assertEqual('a', d2r1)
                self.assertEqual('b', d2r2)
                self.assertEqual('c', d2r3)
                self.assertEqual('d', d2r4)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldTwoDeferredWithMultipleResultsParallelCompletelyMixed(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1, 2, 3, 4], io_loop=self.io_loop)
                d2 = DeferredMock(['a', 'b', 'c', 'd'], io_loop=self.io_loop)
                d1r1 = yield d1
                d2r1 = yield d2
                d2r2 = yield d2
                d1r2 = yield d1
                d1r3 = yield d1
                d2r3 = yield d2
                d2r4 = yield d2
                d1r4 = yield d1
                self.assertEqual(1, d1r1)
                self.assertEqual(2, d1r2)
                self.assertEqual(3, d1r3)
                self.assertEqual(4, d1r4)
                self.assertEqual('a', d2r1)
                self.assertEqual('b', d2r2)
                self.assertEqual('c', d2r3)
                self.assertEqual('d', d2r4)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_YieldDeferredWithSingleError(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d = DeferredMock([ValueError()], io_loop=self.io_loop)
                try:
                    yield d
                except ValueError:
                    trigger.toggle()
                finally:
                    self.stop()
            test()
            self.wait()

    def test_YieldDeferredWithSingleValueAndError(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d = DeferredMock([1, ValueError()], io_loop=self.io_loop)
                r1 = None
                try:
                    r1 = yield d
                    yield d
                except ValueError:
                    trigger.toggle()
                finally:
                    self.assertEqual(1, r1)
                    self.stop()
            test()
            self.wait()

    def test_YieldDeferredWithSingleErrorAndValue(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d = DeferredMock([ValueError(), 1], io_loop=self.io_loop)
                try:
                    yield d
                except ValueError:
                    trigger.toggle()
                finally:
                    r1 = yield d
                    self.assertEqual(1, r1)
                    self.stop()
            test()
            self.wait()

    def test_YieldDeferredWithReturnStatement(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def outer():
                yield DeferredMock(['Outer Message'], io_loop=self.io_loop)
                return_('Return Statement')

            @concurrent.engine
            def inner():
                result = yield outer()
                self.assertEqual('Return Statement', result)
                trigger.toggle()
                self.stop()
            inner()
            self.wait()

    def test_YieldDeferredWithReturnStatementInTheTop(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def outer():
                return_('Return Statement')
                yield DeferredMock(['Outer Message'], io_loop=self.io_loop)
                yield DeferredMock(['Another Outer Message'], io_loop=self.io_loop)

            @concurrent.engine
            def inner():
                result = yield outer()
                self.assertEqual('Return Statement', result)
                trigger.toggle()
                self.stop()
            inner()
            self.wait()

    def test_YieldDeferredWithReturnStatementInTheMiddle(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def outer():
                yield DeferredMock(['Outer Message'], io_loop=self.io_loop)
                return_('Return Statement')
                yield DeferredMock(['Another Outer Message'], io_loop=self.io_loop)

            @concurrent.engine
            def inner():
                result = yield outer()
                self.assertEqual('Return Statement', result)
                trigger.toggle()
                self.stop()
            inner()
            self.wait()

    def test_PropagateErrorsInNestedDeferred(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def outer():
                if True:
                    raise ValueError('Test Error')
                else:
                    yield DeferredMock(['Never Reached Outer Message'], io_loop=self.io_loop)

            @concurrent.engine
            def inner():
                try:
                    yield outer()
                except ValueError:
                    trigger.toggle()
                finally:
                    self.stop()
            inner()
            self.wait()


class AllTestCase(AsyncTestCase):
    os.environ.setdefault('ASYNC_TEST_TIMEOUT', '0.5')

    def test_AllSingleDeferred(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d = DeferredMock([1], io_loop=self.io_loop)
                result = yield All([d])
                self.assertEqual([1], result)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_AllMultipleDeferreds(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                d1 = DeferredMock([1], io_loop=self.io_loop)
                d2 = DeferredMock([2], io_loop=self.io_loop)
                d3 = DeferredMock([3], io_loop=self.io_loop)
                result = yield All([d1, d2, d3])
                self.assertEqual([1, 2, 3], result)
                trigger.toggle()
                self.stop()
            test()
            self.wait()

    def test_AllSingleDeferredWithError(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                try:
                    d = DeferredMock([ValueError('Error message')], io_loop=self.io_loop)
                    yield All([d])
                except AllError as err:
                    self.assertEqual(1, len(err.results))
                    self.assertTrue(isinstance(err.results[0], ValueError))
                    self.assertEqual('Error message', err.results[0].message)
                    trigger.toggle()
                finally:
                    self.stop()
            test()
            self.wait()

    def test_AllMultipleDeferredWithError(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                try:
                    d1 = DeferredMock([ValueError()], io_loop=self.io_loop)
                    d2 = DeferredMock([Exception()], io_loop=self.io_loop)
                    d3 = DeferredMock([SyntaxError()], io_loop=self.io_loop)
                    yield All([d1, d2, d3])
                except AllError as err:
                    self.assertEqual(3, len(err.results))
                    self.assertTrue(isinstance(err.results[0], ValueError))
                    self.assertTrue(isinstance(err.results[1], Exception))
                    self.assertTrue(isinstance(err.results[2], SyntaxError))
                    trigger.toggle()
                finally:
                    self.stop()
            test()
            self.wait()

    def test_AllMultipleDeferredMixed(self):
        with trigger_check(self) as trigger:
            @concurrent.engine
            def test():
                try:
                    d1 = DeferredMock([ValueError()], io_loop=self.io_loop)
                    d2 = DeferredMock(['Ok'], io_loop=self.io_loop)
                    d3 = DeferredMock([123], io_loop=self.io_loop)
                    yield All([d1, d2, d3])
                except AllError as err:
                    self.assertEqual(3, len(err.results))
                    self.assertTrue(isinstance(err.results[0], ValueError))
                    self.assertEqual('Ok', err.results[1])
                    self.assertEqual(123, err.results[2])
                    trigger.toggle()
                finally:
                    self.stop()
            test()
            self.wait()