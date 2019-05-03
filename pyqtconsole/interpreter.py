# -*- coding: utf-8 -*-
import sys
import contextlib

from code import InteractiveConsole

from .qt.QtCore import QObject, Slot

try:
    from builtins import exit       # py3
except ImportError:
    from __builtin__ import exit    # py2


class PythonInterpreter(QObject, InteractiveConsole):

    def __init__(self, stdin, stdout, local = {}):
        QObject.__init__(self)
        InteractiveConsole.__init__(self, local)
        self.local_ns = local
        self.local_ns['exit'] = exit
        self.stdin = stdin
        self.stdout = stdout

        self._running = True
        self._last_input = ''
        self._more = False
        self._current_line = 0
        self._executing = False

        self._inp = 'IN [%s]: '
        self._morep = '...: '
        self._outp = 'OUT[%s]: '
        self._p = self._inp % self._current_line
        self._print_in_prompt()

    def _update_in_prompt(self, _more, _input):
        # We need to show the more prompt of the input was incomplete
        # If the input is complete increase the input number and show
        # the in prompt
        if not _more:
            # Only increase the input number if the input was complete
            # last prompt was the more prompt (and we know that we don't have
            # more input to expect). Obviously do not increase for CR
            if _input != '\n' or self._p == self._morep:
                self._current_line += 1

            self._p = self._inp % self._current_line
        else:
            self._p = (len(self._p) - len(self._morep)) * ' ' + self._morep

    def _print_in_prompt(self):
        self.stdout.write(self._p)

    def executing(self):
        return self._executing

    def push(self, line):
        return InteractiveConsole.push(self, line)

    def runcode(self, code):
        self._executing = True

        # Redirect IO and disable excepthook, this is the only place were we
        # redirect IO, since we don't how IO is handled within the code we
        # are running. Same thing for the except hook, we don't know what the
        # user are doing in it.
        try:
            with redirected_io(self.stdout), disabled_excepthook():
                return InteractiveConsole.runcode(self, code)
        except SystemExit:
            self.exit()
        finally:
            self._executing = False

    def raw_input(self, prompt=None):
        line = self.stdin.readline()

        if line != '\n':
            line = line.strip('\n')

        return line

    def write(self, data):
        self.stdout.write(data)

    def showtraceback(self):
        type_, value, tb = sys.exc_info()
        self.stdout.write('\n')

        if type_ == KeyboardInterrupt:
            self.stdout.write('KeyboardInterrupt\n')
        else:
            InteractiveConsole.showtraceback(self)

        self.stdout.write('\n')

    def showsyntaxerror(self, filename):
        self.stdout.write('\n')
        InteractiveConsole.showsyntaxerror(self, filename)
        self.stdout.write('\n')

    @Slot(str)
    def recv_line(self, line):
        self._last_input = line
        self._more = self.push(line)
        self._update_in_prompt(self._more, self._last_input)
        self._print_in_prompt()

    def handle_ctrl_c(self):
        self.resetbuffer()
        self._last_input = '\n'
        self._more = False
        self.stdout.write('^C\n')
        self._update_in_prompt(self._more, self._last_input)
        self._print_in_prompt()

    def exit(self):
        if self._running:
            self._running = False
            self.stdout.close()


@contextlib.contextmanager
def disabled_excepthook():
    """Run code with the exception hook temporarily disabled."""
    old_excepthook = sys.excepthook
    sys.excepthook = sys.__excepthook__

    try:
        yield
    finally:
        # If the code we did run did change sys.excepthook, we leave it
        # unchanged. Otherwise, we reset it.
        if sys.excepthook is sys.__excepthook__:
            sys.excepthook = old_excepthook


@contextlib.contextmanager
def redirected_io(stdout):
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = stdout
    sys.stderr = stdout
    try:
        yield
    finally:
        if sys.stdout is stdout:
            sys.stdout = old_stdout
        if sys.stderr is stdout:
            sys.stderr = old_stderr
