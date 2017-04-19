from __future__ import division, absolute_import, print_function

import os
import sys
from tempfile import TemporaryFile

from numpy.distutils import exec_command
from numpy.distutils.exec_command import get_pythonexe
from numpy.testing import TestCase, run_module_suite, tempdir

# In python 3 stdout, stderr are text (unicode compliant) devices, so to
# emulate them import StringIO from the io module.
if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from StringIO import StringIO

class redirect_stdout(object):
    """Context manager to redirect stdout for exec_command test."""
    def __init__(self, stdout=None):
        self._stdout = stdout or sys.stdout

    def __enter__(self):
        self.old_stdout = sys.stdout
        sys.stdout = self._stdout

    def __exit__(self, exc_type, exc_value, traceback):
        self._stdout.flush()
        sys.stdout = self.old_stdout
        # note: closing sys.stdout won't close it.
        self._stdout.close()

class redirect_stderr(object):
    """Context manager to redirect stderr for exec_command test."""
    def __init__(self, stderr=None):
        self._stderr = stderr or sys.stderr

    def __enter__(self):
        self.old_stderr = sys.stderr
        sys.stderr = self._stderr

    def __exit__(self, exc_type, exc_value, traceback):
        self._stderr.flush()
        sys.stderr = self.old_stderr
        # note: closing sys.stderr won't close it.
        self._stderr.close()

class emulate_nonposix(object):
    """Context manager to emulate os.name != 'posix' """
    def __init__(self, osname='non-posix'):
        self._new_name = osname

    def __enter__(self):
        self._old_name = os.name
        os.name = self._new_name

    def __exit__(self, exc_type, exc_value, traceback):
        os.name = self._old_name


def test_exec_command_stdout():
    # Regression test for gh-2999 and gh-2915.
    # There are several packages (nose, scipy.weave.inline, Sage inline
    # Fortran) that replace stdout, in which case it doesn't have a fileno
    # method.  This is tested here, with a do-nothing command that fails if the
    # presence of fileno() is assumed in exec_command.

    # The code has a special case for posix systems, so if we are on posix test
    # both that the special case works and that the generic code works.

    # Test posix version:
    with redirect_stdout(StringIO()):
        with redirect_stderr(TemporaryFile()):
            exec_command.exec_command("cd '.'")

    if os.name == 'posix':
        # Test general (non-posix) version:
        with emulate_nonposix():
            with redirect_stdout(StringIO()):
                with redirect_stderr(TemporaryFile()):
                    exec_command.exec_command("cd '.'")

def test_exec_command_stderr():
    # Test posix version:
    with redirect_stdout(TemporaryFile(mode='w+')):
        with redirect_stderr(StringIO()):
            exec_command.exec_command("cd '.'")

    if os.name == 'posix':
        # Test general (non-posix) version:
        with emulate_nonposix():
            with redirect_stdout(TemporaryFile()):
                with redirect_stderr(StringIO()):
                    exec_command.exec_command("cd '.'")


class TestExecCommand(TestCase):
    def setUp(self):
        self.pyexe = get_pythonexe()

    def check_nt(self, **kws):
        s, o = exec_command.exec_command('echo path=%path%')
        self.assertEqual(s, 0)
        self.assertNotEqual(o, '')

        s, o = exec_command.exec_command(
         '"%s" -c "import sys;sys.stderr.write(sys.platform)"' % self.pyexe)
        self.assertEqual(s, 0)
        self.assertEqual(o, 'win32')

    def check_posix(self, **kws):
        s, o = exec_command.exec_command("echo Hello", **kws)
        self.assertEqual(s, 0)
        self.assertEqual(o, 'Hello')

        s, o = exec_command.exec_command('echo $AAA', **kws)
        self.assertEqual(s, 0)
        self.assertEqual(o, '')

        s, o = exec_command.exec_command('echo "$AAA"', AAA='Tere', **kws)
        self.assertEqual(s, 0)
        self.assertEqual(o, 'Tere')

        s, o = exec_command.exec_command('echo "$AAA"', **kws)
        self.assertEqual(s, 0)
        self.assertEqual(o, '')

        if 'BBB' not in os.environ:
            os.environ['BBB'] = 'Hi'
            s, o = exec_command.exec_command('echo "$BBB"', **kws)
            self.assertEqual(s, 0)
            self.assertEqual(o, 'Hi')

            s, o = exec_command.exec_command('echo "$BBB"', BBB='Hey', **kws)
            self.assertEqual(s, 0)
            self.assertEqual(o, 'Hey')

            s, o = exec_command.exec_command('echo "$BBB"', **kws)
            self.assertEqual(s, 0)
            self.assertEqual(o, 'Hi')

            del os.environ['BBB']

            s, o = exec_command.exec_command('echo "$BBB"', **kws)
            self.assertEqual(s, 0)
            self.assertEqual(o, '')


        s, o = exec_command.exec_command('this_is_not_a_command', **kws)
        self.assertNotEqual(s, 0)
        self.assertNotEqual(o, '')

        s, o = exec_command.exec_command('echo path=$PATH', **kws)
        self.assertEqual(s, 0)
        self.assertNotEqual(o, '')

        s, o = exec_command.exec_command(
             '"%s" -c "import sys,os;sys.stderr.write(os.name)"' %
             self.pyexe, **kws)
        self.assertEqual(s, 0)
        self.assertEqual(o, 'posix')

    def check_basic(self, *kws):
        s, o = exec_command.exec_command(
                     '"%s" -c "raise \'Ignore me.\'"' % self.pyexe, **kws)
        self.assertNotEqual(s, 0)
        self.assertNotEqual(o, '')

        s, o = exec_command.exec_command(
             '"%s" -c "import sys;sys.stderr.write(\'0\');'
             'sys.stderr.write(\'1\');sys.stderr.write(\'2\')"' %
             self.pyexe, **kws)
        self.assertEqual(s, 0)
        self.assertEqual(o, '012')

        s, o = exec_command.exec_command(
                 '"%s" -c "import sys;sys.exit(15)"' % self.pyexe, **kws)
        self.assertEqual(s, 15)
        self.assertEqual(o, '')

        s, o = exec_command.exec_command(
                     '"%s" -c "print(\'Heipa\'")' % self.pyexe, **kws)
        self.assertEqual(s, 0)
        self.assertEqual(o, 'Heipa')

    def check_execute_in(self, **kws):
        with tempdir() as tmpdir:
            fn = "file"
            tmpfile = os.path.join(tmpdir, fn)
            f = open(tmpfile, 'w')
            f.write('Hello')
            f.close()

            s, o = exec_command.exec_command(
                 '"%s" -c "f = open(\'%s\', \'r\'); f.close()"' %
                 (self.pyexe, fn), **kws)
            self.assertNotEqual(s, 0)
            self.assertNotEqual(o, '')
            s, o = exec_command.exec_command(
                     '"%s" -c "f = open(\'%s\', \'r\'); print(f.read()); '
                     'f.close()"' % (self.pyexe, fn), execute_in=tmpdir, **kws)
            self.assertEqual(s, 0)
            self.assertEqual(o, 'Hello')

    def test_basic(self):
        with redirect_stdout(StringIO()):
            with redirect_stderr(StringIO()):
                if os.name == "posix":
                    self.check_posix(use_tee=0)
                    self.check_posix(use_tee=1)
                elif os.name == "nt":
                    self.check_nt(use_tee=0)
                    self.check_nt(use_tee=1)
                self.check_execute_in(use_tee=0)
                self.check_execute_in(use_tee=1)


if __name__ == "__main__":
    run_module_suite()
