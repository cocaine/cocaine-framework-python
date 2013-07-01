#!/usr/bin/env python

import opster
import imp

cocaine_tool = imp.load_module("cocaine_tool",
                               open("scripts/cocaine-tool", "rw"),
                               "scripts/cocaine_tool",
                               ("", "r", imp.PY_SOURCE))


class Man(object):

    def __init__(self, name, version):
        self._header = [".TH %s %s" % (name, version)] 
        self._name = [".SH NAME \n%s" % name]
        self._description = [".SH DESCRIPTION"]
        self._synopsis = [".SH SYNOPSIS\n"]
        self._body = [".SH COMMANDS\n"]
        self._author = [".SH AUTHORS\n"]
        self.currpath = ""

    def add_author(self, author):
        self._author.append(author)

    def add_description(self, description):
        self._description.append(description)

    def generate(self):
        print '\n'.join(self._header)
        print '\n'.join(self._name)
        print '\n'.join(self._description)
        print ' '.join(self._synopsis)
        print '\n'.join(self._body)
        print '\n'.join(self._author)

    def describe_dispatcher(self, d, path=""):
        for k, v in d.cmdtable.iteritems():
            obj, opts, usage = v
            if isinstance(obj, opster.Dispatcher):
                self.describe_dispatcher(v[0], k)
            else:
                self.describe_action(k, obj, opts, usage, "cocaine-tool " + path if path else "cocaine-tool")

    def describe_action(self, name, func, opts, usage, path):
        def gen_synopsis_for_opt(opt):
            if opt.default:
                return r"[\fB--%s\fR]" % opt.name
            else:
                return r"\fB--%s\fR" % opt.name
        self._synopsis.append(' '.join([path, name]) + ' '
                              + ' '.join(reversed(map(gen_synopsis_for_opt, opts)))
                              + '\n')
        self._body.append(r"\fI%s %s\fR %s" % (path, name, func.__doc__.strip('\n')))
        for opt in opts:
            l = r"\fb-%s\fR, " % opt.short if opt.short else ""
            l += r"\fb--%s\fR " % opt.name if opt.name else ""
            l += opt.helpmsg
            l += r" (default: %s)" % opt.default if opt.default else ""
            self._body.append(l)
            self._body.append(".PP")

m = Man("cocaine-tool", 5)
m.add_description(cocaine_tool.__doc__ if cocaine_tool.__doc__ is not None else "")
m.add_author(cocaine_tool.__author__)
m.describe_dispatcher(cocaine_tool.d)
m.generate()
