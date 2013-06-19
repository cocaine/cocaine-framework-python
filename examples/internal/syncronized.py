from cocaine.services import Service
from cocaine.exceptions import TimeoutError

__author__ = 'EvgenySafronov <division494@gmail.com>'


if __name__ == '__main__':
    s = Service('node')
    # while True:
    try:
        info = s.info().then(lambda r: r.get()).then(lambda r: r.get()).then(lambda r: r.get()).get()
        print(info)
    except TimeoutError as err:
        print(err)
    except Exception as err:
        print(err, type(err))
