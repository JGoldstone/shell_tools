import unittest
from tempfile import TemporaryDirectory

from fileseq import FileSequence


from shell_tools.frames import FrameSequence


class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertEqual(True, False)  # add assertion here

    def test_empty_sequence(self):
        with TemporaryDirectory(prefix='test_frame_sequence') as d:
            s = FrameSequence(d)
            self.assertEqual(FileSequence())
            self.assertEqual('', str(s))
            self.assertEqual("FileSequence('')", repr(s))

if __name__ == '__main__':
    unittest.main()
