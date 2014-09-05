from __future__ import absolute_import
import unittest
import logging
import msgpack
import sys

from tornado.testing import AsyncTestCase
from cocaine.futures import chain

from cocaine.futures.chain import Chain
from cocaine.testing.mocks import ServiceMock, checker
from cocaine.exceptions import ChokeEvent
from cocaine.asio.exceptions import TimeoutError
from cocaine.decorators.http import _tornado_request_wrapper


__author__ = 'Evgeny Safronov <division494@gmail.com>'

formatter = logging.Formatter('%(levelname)-8s: %(message)s')
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)

logNames = [
    __name__,
    'cocaine.futures.chain',
    'cocaine.testing.mocks',
]

for logName in logNames:
    log = logging.getLogger(logName)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    log.addHandler(ch)


class HotTestCase(AsyncTestCase):
    T = Chain

    def test_NoChunks_MultipleYield(self):
        completed = [0]

        @chain.source
        def compare(s):
            yield s.execute()
            try:
                completed[0] += 1
                yield
            except ChokeEvent:
                completed[0] += 1
            self.stop()
        s = ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop)
        compare(s)
        self.wait(timeout=0.5)
        self.assertEqual(completed[0], 2)


class AsynchronousApiTestCase(AsyncTestCase):
    T = Chain

    def test_NoChunks_Yield(self):
        completed = [False]

        @chain.source
        def compare(s):
            yield s.execute()
            completed[0] = True
            self.stop()
        s = ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop)
        compare(s)
        self.wait()
        self.assertTrue(completed[0])

    def test_SingleChunk_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()

        def firstStep(futureResult):
            r = futureResult.get()
            return r * 2
        f.then(firstStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertEqual(4, r.get()),
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()

        def firstStep(futureResult):
            r = futureResult.get()
            r *= 2
            return r
        f.then(firstStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleSyncChunk_SingleThen(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
        ]
        check = checker(expected, self)
        f = Chain([lambda: 1], ioLoop=self.io_loop)
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleSyncChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertEqual(6, r.get()),
        ]
        check = checker(expected, self)
        f = Chain([lambda: 2], ioLoop=self.io_loop)

        def firstStep(futureResult):
            r = futureResult.get()
            r *= 3
            return r
        f.then(firstStep).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleErrorChunk_SingleThen(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
        ]
        check = checker(expected, self)

        def firstStep():
            raise Exception('Actual')

        f = Chain([firstStep], ioLoop=self.io_loop)
        f.then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleErrorChunk_MultipleThen(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
        ]
        check = checker(expected, self)

        def firstStep():
            raise Exception('Actual')

        def secondStep(futureResult):
            futureResult.get()
            self.fail('This one should never be seen by anyone')

        f = Chain([firstStep], ioLoop=self.io_loop)
        f.then(secondStep).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_Middleman(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
        ]
        check = checker(expected, self)

        def middleMan(result):
            return result.get() + 1
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait(timeout=0.5)
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_ErrorMiddleman(self):
        expected = [
            lambda r: self.assertRaises(ValueError, r.get),
            lambda r: self.assertRaises(ValueError, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            raise ValueError('Middleman')
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleThen_ErrorMiddlemanWithValueUnpacking(self):
        expected = [
            lambda r: self.assertRaises(ValueError, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            raise ValueError('Middleman')
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunks_MultipleThen_ErrorMiddleman(self):
        expected = [
            lambda r: self.assertEqual(2, r.get()),
            lambda r: self.assertRaises(ValueError, r.get),
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            if result.get() == 2:
                raise ValueError('Middleman')
            else:
                return result.get() * 2
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_SingleThen_YieldMiddleman(self):
        expected = [
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            yield 'String that won\'t be seen by anyone'
            yield 3
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleChainItems_OnlyCoroutinesProcessing(self):
        expected = [
            lambda r: self.assertEqual(4, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def firstStep(result):
            r = result.get()
            yield 'String that won\'t be seen by anyone'
            yield r * 2

        def secondStep(result):
            yield result.get() * 2

        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(firstStep).then(secondStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleChainItems_MixedProcessing1(self):
        expected = [
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def firstStep(result):
            r = result.get()
            return r * 2

        def secondStep(result):
            yield result.get() * 3

        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(firstStep).then(secondStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_MultipleChainItems_MixedProcessing2(self):
        expected = [
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def firstStep(result):
            yield result.get() * 3

        def secondStep(result):
            r = result.get()
            return r * 2

        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.then(firstStep).then(secondStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldMiddleman(self):
        expected = [
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertEqual(6, r.get()),
            lambda r: self.assertEqual(9, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            r = result.get()
            yield 'This string won\'t be seen by anyone'
            yield r * 3
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldAsyncMiddleman(self):
        expected = [
            lambda r: self.assertEqual([1, 2], r.get()),
            lambda r: self.assertEqual([2, 3], r.get()),
            lambda r: self.assertEqual([3, 4], r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            r = result.get()
            s1 = yield ServiceMock(chunks=[r, r + 1], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            yield [s1, s2]
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_SingleThen_YieldAsyncDoubleMiddlemanWithLessChunks(self):
        expected = [
            lambda r: self.assertEqual([4, 5, 6], r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.002).execute()
            s2 = yield
            s3 = yield ServiceMock(chunks=[6], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            yield [s1, s2, s3]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_SingleChunk_SingleThen_YieldAsyncDoubleMiddlemanWithMoreChunks(self):
        expected = [
            lambda r: self.assertEqual([4, 5, 6, 7, 8], r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            s3 = yield ServiceMock(chunks=[6, 7, 8], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s4 = yield
            s5 = yield
            yield [s1, s2, s3, s4, s5]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_YieldAsyncMiddlemanExtraChunkResultsInChokeEvent(self):
        expected = [
            lambda r: self.assertRaises(ChokeEvent, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            # This one will lead to the ChokeEvent
            s3 = yield
            yield [s1, s2, s3]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_YieldAsyncMiddlemanExtraChunksResultsInChokeEventForever(self):
        expected = [
            lambda r: self.assertRaises(ChokeEvent, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, 5], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            s2 = yield
            # This one will lead to the ChokeEvent
            s3 = yield
            s4 = yield
            yield [s1, s2, s3, s4]
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.01).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldErrorMiddleman(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertEqual(3, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            r = result.get()
            if r == 2:
                raise Exception('=(')
            yield r
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_SingleThen_YieldAsyncErrorMiddleman(self):
        expected = [
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertRaises(Exception, r.get),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def middleMan(result):
            result.get()
            s1 = yield ServiceMock(chunks=[4, Exception(), 6], T=self.T, ioLoop=self.io_loop, interval=0.001).execute()
            # Here exception comes
            s2 = yield
            s3 = yield
            print('This should not be seen!', s1, s2, s3)
            yield 1
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_Chain_YieldEmptyServiceInside(self):
        expected = [
            lambda r: self.assertEqual('Ok', r.get()),
        ]
        check = checker(expected, self)

        def firstStep():
            yield ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop, interval=0.002).execute()
            yield 'Ok'

        f = Chain([firstStep], ioLoop=self.io_loop)
        f.then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_Chain_YieldEmptyServicesInside(self):
        expected = [
            lambda r: self.assertEqual('Ok', r.get()),
        ]
        check = checker(expected, self)

        def firstStep():
            yield ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop, interval=0.002).execute()
            yield ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop, interval=0.002).execute()
            yield 'Ok'

        f = Chain([firstStep], ioLoop=self.io_loop)
        f.then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_Chain_YieldChainAndEmptyServiceInside(self):
        expected = [
            lambda r: self.assertEqual(1, r.get()),
        ]
        check = checker(expected, self)

        def firstStep():
            r1 = yield Chain([lambda: 1], ioLoop=self.io_loop)
            yield ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop, interval=0.002).execute()
            yield r1

        f = Chain([firstStep], ioLoop=self.io_loop)
        f.then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_YieldChainAndEmptyServiceInside_MultipleSteps(self):
        expected = [
            lambda r: self.assertEqual('Really Ok', r.get()),
        ]
        check = checker(expected, self)

        def firstStep():
            yield ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop, interval=0.004).execute()
            yield ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop, interval=0.002).execute()
            yield 'Ok'

        def secondStep(result):
            yield 'Really ' + result.get()

        f = Chain([firstStep], ioLoop=self.io_loop).then(secondStep)
        f.then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_MultipleChunk_MultipleThen_SyncTransformation(self):
        expected = [
            lambda r: self.assertEqual({'app': 'info'}, r.get()),
            lambda r: self.assertRaises(ChokeEvent, r.get),
        ]
        check = checker(expected, self)

        def firstStep(result):
            r = result.get()
            return {'app': r}

        def secondStep(result):
            r = result.get()
            return r

        s = ServiceMock(chunks=['info'], T=self.T, ioLoop=self.io_loop).execute()
        s.then(firstStep).then(secondStep).then(check)
        self.wait()
        self.assertTrue(len(expected) == 0)

    def test_All(self):
        completed = [False]

        @chain.source
        def func():
            r1, r2 = yield chain.All([s1.execute(), s2.execute()])
            self.assertEqual([r1, r2], ['1', '2'])
            completed[0] = True
            self.stop()

        s1 = ServiceMock(chunks=['1'], T=self.T, ioLoop=self.io_loop)
        s2 = ServiceMock(chunks=['2'], T=self.T, ioLoop=self.io_loop)
        func()
        self.wait()
        self.assertTrue(completed[0])

    def test_ComplexAll(self):
        completed = [False]

        @chain.source
        def func():
            r1, r2 = yield chain.All([s1.execute(), s2.execute()])
            self.assertEqual([r1, r2], ['1', ['2', '3']])
            completed[0] = True
            self.stop()

        s1 = ServiceMock(chunks=['1'], T=self.T, ioLoop=self.io_loop)
        s2 = ServiceMock(chunks=['2', '3'], T=self.T, ioLoop=self.io_loop)
        func()
        self.wait()
        self.assertTrue(completed[0])

    @unittest.skip('Broken')
    def test_AllWithNones(self):
        completed = [False]

        @chain.source
        def func():
            r1, r2 = yield chain.All([s1.execute(), s2.execute()])
            self.assertEqual([r1, r2], [None, None])
            completed[0] = True
            self.stop()

        s1 = ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop)
        s2 = ServiceMock(chunks=[], T=self.T, ioLoop=self.io_loop)
        func()
        self.wait(timeout=0.5)
        self.assertTrue(completed[0])


class SynchronousApiTestCase(AsyncTestCase):
    T = Chain

    def test_GetSingleChunk(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        r = f.get()
        self.assertEqual(1, r)

    def test_GetMultipleChunks(self):
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        r1 = f.get()
        r2 = f.get()
        r3 = f.get()
        self.assertEqual(1, r1)
        self.assertEqual(2, r2)
        self.assertEqual(3, r3)

    def test_GetSingleChunkMultipleTimes(self):
        s = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop)
        s.execute().get()
        r2 = s.execute().get()
        self.assertEqual(1, r2)

    def test_GetMultipleChunksMultipleTimes(self):
        s = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop)
        f1 = s.execute()
        f1.get()
        f1.get()
        f1.get()

        f2 = s.execute()
        r21 = f2.get()
        r22 = f2.get()
        r23 = f2.get()
        self.assertEqual(1, r21)
        self.assertEqual(2, r22)
        self.assertEqual(3, r23)

    def test_GetSingleErrorChunk(self):
        f = ServiceMock(chunks=[Exception('Oops')], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(Exception, f.get)

    def test_GetMultipleErrorChunks(self):
        f = ServiceMock(chunks=[ValueError('Oops1'), IOError('Oops2')], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(ValueError, f.get)
        self.assertRaises(IOError, f.get)

    def test_GetMultipleMixChunks(self):
        f = ServiceMock(chunks=[ValueError('Oops1'), 1, IOError('Oops2')], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(ValueError, f.get)
        self.assertEqual(1, f.get())
        self.assertRaises(IOError, f.get)

    def test_GetMultipleMixChunksWithComplexChain(self):
        def middleMan(result):
            r = result.get()
            if r == 2:
                raise Exception('=(')
            yield r
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.then(middleMan)
        self.assertEqual(1, f.get())
        self.assertRaises(Exception, f.get)
        self.assertEqual(3, f.get())

    def test_GetSingleChunkTimeout(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.2).execute()
        self.assertRaises(TimeoutError, f.get, 0.1)

    def test_GetValueErrors(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        self.assertRaises(ValueError, f.get, 0)
        self.assertRaises(ValueError, f.get, -1.0)
        self.assertRaises(ValueError, f.get, 0.0009)
        self.assertRaises(TypeError, f.get, 'str')
        self.assertRaises(TypeError, f.get, '0.1')

    def test_GetExtraChunksResultsInChokeEvent(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        r = f.get()
        self.assertEqual(1, r)
        self.assertRaises(ChokeEvent, f.get)
        self.assertRaises(ChokeEvent, f.get)

    def test_GetSingleChunkAfterWaiting(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.wait()
        r = f.get()
        self.assertEqual(1, r)

    def test_GetSingleChunkMultipleTimesAfterWaiting(self):
        s = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop)
        f1 = s.execute()
        f1.wait()
        f1.get()
        f2 = s.execute()
        f2.wait()
        r2 = f2.get()
        self.assertEqual(1, r2)

    def test_GetSingleChunkAfterMultipleWaiting(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f.wait()
        f.wait()
        f.wait()
        r = f.get()
        self.assertEqual(1, r)

    def test_GetMultipleChunksAfterMultipleWaiting(self):
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        f.wait()
        f.wait()
        r1 = f.get()
        f.wait()
        f.wait()
        f.wait()
        r2 = f.get()
        r3 = f.get()
        self.assertEqual(1, r1)
        self.assertEqual(2, r2)
        self.assertEqual(3, r3)

    def test_HasPendingResult(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        self.assertFalse(f.hasPendingResult())
        f.wait()
        self.assertTrue(f.hasPendingResult())

    def test_MagicHasPendingResult(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        self.assertFalse(bool(f))
        f.wait()
        self.assertTrue(bool(f))

    def test_WaitWithTimeout(self):
        f = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop, interval=0.1).execute()
        f.wait(0.050)
        self.assertTrue(len(f._pending) == 0)
        f.wait(0.040)
        self.assertTrue(len(f._pending) == 0)
        f.wait(0.011)
        self.assertFalse(len(f._pending) == 0)

    def test_Generator(self):
        chain = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        collect = []
        for result in chain:
            collect.append(result)
        self.assertEqual([1, 2, 3], collect)

    def test_PartialGenerator(self):
        f = ServiceMock(chunks=[1, 2, 3], T=self.T, ioLoop=self.io_loop).execute()
        collect = [f.get()]
        for r in f:
            collect.append(r)
        self.assertEqual([1, 2, 3], collect)

    def test_GetMultipleChunksDeferredly(self):
        f1 = ServiceMock(chunks=[1], T=self.T, ioLoop=self.io_loop).execute()
        f2 = ServiceMock(chunks=[2], T=self.T, ioLoop=self.io_loop).execute()
        self.assertEqual(2, f2.get())
        self.assertEqual(1, f1.get())

    def test_wsgi(self):
        req = ['POST',
               '/blabla?arg=1',
               '1.1',
               [['User-Agent', 'curl/7.22.0 (x86_64-pc-linux-gnu) libcurl/7.22.0 OpenSSL/1.0.1 zlib/1.2.3.4 libidn/1.23 librtmp/2.3'],
                ['Host', 'localhost:8080'],
                ['Accept', '*/*'],
                ['Content-Length', '6'],
                ['Content-Type', 'application/x-www-form-urlencoded']], 'dsdsds']
        request = _tornado_request_wrapper(msgpack.packb(req))
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.protocol, "http")

if __name__ == '__main__':
    unittest.main()
