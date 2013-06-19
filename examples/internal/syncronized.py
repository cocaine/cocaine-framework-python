from cocaine.services import Service
from cocaine.exceptions import TimeoutError

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    s = Service('node')
    try:
        info = s.info().get(timeout=0.001)
        print(info)
    except TimeoutError as err:
        print(1, err)
    except Exception as err:
        print(err, type(err))
