#
#    Copyright (c) 2012+ Anton Tyurin <noxiouz@yandex.ru>
#    Copyright (c) 2011-2014 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

from cocaine.detail import defaults

from nose import tools


def test_parse_locators_v1():
    locators = "host1:10053,127.0.0.1:10054,ff:fdf::fdfd:10054"
    parsed = defaults.parse_locators_v1(locators)
    assert parsed == [("host1", 10053), ("127.0.0.1", 10054), ("ff:fdf::fdfd", 10054)], parsed


def test_parse_locators_v0():
    locators = "127.0.0.1:10054"
    parsed = defaults.parse_locators_v0(locators)
    assert parsed == [("127.0.0.1", 10054)], parsed


def test_defaults_v1():
    argv = ["--locator", "host1:10053,127.0.0.1:10054",
            "--uuid", "uuid", "--protocol", "1",
            "--endpoint", "/var/run/cocaine/sock"]

    opts = defaults.DefaultOptions(argv)
    assert opts.protocol == 1, opts.protocol
    assert opts.uuid == "uuid", opts.uuid
    assert opts.app == defaults.DEFAULT_APPNAME, opts.app
    assert opts.endpoint == "/var/run/cocaine/sock", opts.endpoint
    assert opts.locators == [("host1", 10053), ("127.0.0.1", 10054)], opts.locators


def test_defaults_v0():
    argv = ["--locator", "host1:10053",
            "--uuid", "uuid", "--app", "APP",
            "--endpoint", "/var/run/cocaine/sock"]

    opts = defaults.DefaultOptions(argv)
    assert opts.protocol == 0, opts.protocol
    assert opts.uuid == "uuid", opts.uuid
    assert opts.endpoint == "/var/run/cocaine/sock", opts.endpoint
    assert opts.locators == [("host1", 10053)], opts.locators
    assert opts.app == "APP", opts.app


@tools.raises(defaults.MalformedArgs)
def test_malfomed_args():
    argv = ["--locator"]
    opts = defaults.DefaultOptions(argv)
    opts.locators
