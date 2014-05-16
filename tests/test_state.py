import unittest

from cocaine.services.state import StateBuilder, RootState, State

__author__ = 'Evgeny Safronov <division494@gmail.com>'


class StateTestCase(unittest.TestCase):
    def test_state_builder(self):
        api = {
            0: (
                'enqueue', {
                    0: ('write', {}),
                    1: ('close', {})
                }
            ),
            1: ('info', {})
        }

        builder = StateBuilder()
        actual = builder.build(api)

        expected = RootState()
        state = State(0, 'enqueue', expected)
        State(1, 'info', expected)
        State(0, 'write', state)
        State(1, 'close', state)
        self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
