#!/usr/bin/env python
"""
Shell tool to quickly describe sequences of frames (and debris) in a frame directory
===================

Frame directories are those used either in R&D or production to hold potentially large
sequences of frames, so many that it can be difficult to determine from a simple 'ls'
command exactly what is present. This tools reduces that visual clutter. It can also
be used to identify missing frames, frames that are significantly shorter than the
median (which may have been only partially written), and the starting and ending
frame numbers of a sequence.

"""
from sys import argv, exit, stderr
import os
import argparse
from pathlib import Path

from fileseq import findSequencesOnDisk


# from Blender, supposedly
class BlenderColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


FRAMES_VERSION = 0.1
KNOWN_IMAGE_ESSENCE_CONTAINERS = ('.mov', '.mxf', '.ari', '.dpx', '.exr', 'tif', 'tiff', 'png')


def _print_maybe_with_sequence_first(one_of_many, seq_string, thing):
    if one_of_many:
        print(seq_string, thing)
    else:
        print(thing)


def _seq_in_nuke_style(seq):
    return f"{seq.basename()}%0{seq.zfill()}d{seq.extension()}"


def _interleaved_present_and_missing(seq):
    sub_seqs = seq.split()
    result = []
    while sub_seqs:
        present = sub_seqs.pop(0)
        result.append((present.start(), present.end()))
        if sub_seqs:
            upcoming = sub_seqs[0]
            result.append((present.end() + 1, upcoming.start() - 1))
    return result


def _max_sub_seq_count_width(seq):
    sub_seqs = seq.split()
    return max([len(f"{1 + s.end() - s.start()}") for s in sub_seqs])


class FramesTool(object):

    def __init__(self):
        # These are here to make PyCharm shut up about unresolved attribute references; parse_args would have set them.
        self.sequence_left_substrings = []
        self.include_sequences = True
        self.include_debris = True
        # From here on down, these are mutually exclusive (only one can be specified)
        self.include_missing = False
        self.unique = False
        self.print_pad = False
        self.print_first = False
        self.print_last = False

    def _find_sequences_and_debris(self):
        seqs = findSequencesOnDisk(self.dir)
        if self.sequence_left_substrings:
            seqs = {s for s in seqs if s.basename().startswith(self.sequence_left_substrings)}
        self._image_essence_sequences = {s for s in seqs if s.extension() in KNOWN_IMAGE_ESSENCE_CONTAINERS}
        self._debris = {s.basename() for s in seqs if s not in self._image_essence_sequences}

    def _sub_seq_frame_desc(self, sub_seq, present, max_zfill):
        start_digits = f"{sub_seq[0]}"
        end_digits = f"{sub_seq[1]}"
        if start_digits == end_digits:
            total_field_width = max_zfill + 1 + max_zfill
            leading_pad = f"{' ' * ((total_field_width - len(start_digits)) // 2)}"
            trailing_pad = f"{' ' * (total_field_width - (len(leading_pad) + len(start_digits)))}"
            frames = f"{start_digits}"
        else:
            leading_pad = f"{' ' * (max_zfill - len(start_digits))}"
            trailing_pad = f"{' ' * (max_zfill - len(end_digits))}"
            frames = f"{start_digits}-{end_digits}"
        color = BlenderColors.FAIL if not present else BlenderColors.BOLD
        return f"{leading_pad}{color}{frames}{BlenderColors.ENDC}{trailing_pad}"

    def summarize_frames(self):
        if not self.include_sequences and not self.include_debris:
            return
        self._find_sequences_and_debris()
        num_sequences = len(self._image_essence_sequences)
        if self.unique and num_sequences > 1:
            raise RuntimeError("--unique specified and multiple sequences exist")
        if self.print_pad or self.print_first or self.print_last:
            if not self._image_essence_sequences:
                raise RuntimeError((f" --pad, --first or --last argument given to 'frame' command, but"
                                    f" no sequences were found in the specified directory `{self.dir}'"))
            for seq in self._image_essence_sequences:
                seq_string = _seq_in_nuke_style(seq)
                if self.print_pad:
                    _print_maybe_with_sequence_first(num_sequences > 1, seq_string, seq.frameSet().zfill)
                elif self.print_first:
                    _print_maybe_with_sequence_first(num_sequences > 1, seq_string, seq.frameSet().first)
                else:
                    _print_maybe_with_sequence_first(num_sequences > 1, seq_string, seq.frameSet().last)
            return
        # and now, what you've all been waiting for
        max_zfill = None
        if self.include_sequences and self._image_essence_sequences:
            max_zfill = max([seq.zfill() for seq in self._image_essence_sequences])
            max_subseq_count_width = max([_max_sub_seq_count_width(s) for s in self._image_essence_sequences])
            for seq in self._image_essence_sequences:
                present = True
                sub_seqs = _interleaved_present_and_missing(seq)
                is_first_sub_seq = True
                seq_in_nuke_style = _seq_in_nuke_style(seq)
                for sub_seq in sub_seqs:
                    if (present and self.include_sequences) or (not present and self.include_missing):
                        sub_seq_frames = self._sub_seq_frame_desc(sub_seq, present, max_zfill)
                        sub_seq_count = f"{1 + sub_seq[1] - sub_seq[0]}"
                        sub_seq_count_width = len(sub_seq_count)
                        sub_seq_count_leading_pad = f"{' ' * (max_subseq_count_width - sub_seq_count_width)}"
                        count = f"{sub_seq_count_leading_pad}({sub_seq_count}) "
                        seq_desc = seq_in_nuke_style if is_first_sub_seq else f'{" " * (len(seq_in_nuke_style) // 2)}"'
                        print(f"{sub_seq_frames} {count}{seq_desc}")
                    present = not present
                    is_first_sub_seq = False
        if self.include_debris:
            if max_zfill:
                for thing in self._debris:
                    frame_range_padding = f"{' ' * (max_zfill + 1 + max_zfill)}"
                    count_padding = f"{' ' * (1 + 1 + max_subseq_count_width + 1)}"
                    print(f"{frame_range_padding}{count_padding} {BlenderColors.WARNING}{thing}{BlenderColors.ENDC}")
            else:
                for thing in self._debris:
                    print(f"    {thing}")


# cf. https://stackoverflow.com/questions/11415570/directory-path-types-with-argparse
class PathType(object):
    def __init__(self, exists=True, type_='file', dash_ok=True):
        """
        exists:
            True: a path that does exist
            False: a path that does not exist, in a valid parent directory
            None: don't care
        type_: file, dir, symlink, None, or a function returning True for valid paths
            None: don't care
        dash_ok: whether to allow "-" as stdin/stdout
        """

        assert exists in (True, False, None)
        assert type_ in ('file', 'dir', 'symlink', None) or hasattr(type_, '__call__')

        self._exists = exists
        self._type = type_
        self._dash_ok = dash_ok

    def __call__(self, string):
        if string == '-':
            # the special argument "-" means sys.std{in,out}
            if self._type == 'dir':
                raise argparse.ArgumentTypeError('standard input/output (-) not allowed as directory path')
            elif self._type == 'symlink':
                raise argparse.ArgumentTypeError('standard input/output (-) not allowed as symlink path')
            elif not self._dash_ok:
                raise argparse.ArgumentTypeError('standard input/output (-) not allowed')
        else:
            e = os.path.exists(string)
            if self._exists:
                if not e:
                    raise argparse.ArgumentTypeError("path does not exist: '%s'" % string)

                if self._type is None:
                    pass
                elif self._type == 'file':
                    if not os.path.isfile(string):
                        raise argparse.ArgumentTypeError("path is not a file: '%s'" % string)
                elif self._type == 'symlink':
                    if not os.path.islink(string):
                        raise argparse.ArgumentTypeError("path is not a symlink: '%s'" % string)
                elif self._type == 'dir':
                    if not os.path.isdir(string):
                        raise argparse.ArgumentTypeError("path is not a directory: '%s'" % string)
                elif not self._type(string):
                    raise argparse.ArgumentTypeError("path not valid: '%s'" % string)
            else:
                if not self._exists and e:
                    raise argparse.ArgumentTypeError("path exists: '%s'" % string)

                p = os.path.dirname(os.path.normpath(string)) or '.'
                if not os.path.isdir(p):
                    raise argparse.ArgumentTypeError("parent path is not a directory: '%s'" % p)
                elif not os.path.exists(p):
                    raise argparse.ArgumentTypeError("parent directory does not exist: '%s'" % p)

        return string


if __name__ == '__main__':
    tool = FramesTool()
    # frames_script = argv[0]
    parser = argparse.ArgumentParser(prog='frames')
    parser.add_argument('--version', action='version', version=f"%(prog)s {FRAMES_VERSION}")
    # These act as filters for the set of sequences to examine
    parser.add_argument('--sequences', action=argparse.BooleanOptionalAction, default=True,
                        dest='include_sequences', help='include files recognizably clips or frames')
    parser.add_argument('--debris', action=argparse.BooleanOptionalAction, default=False,
                        dest='include_debris', help='include files not recognizably clips or frames')
    parser.add_argument('dir', type=PathType(exists=True, type_='dir'))
    parser.add_argument('sequence_left_substrings', metavar='substr', type=str, nargs='*',
                        help='left substring filter for sequence(s)')
    # These tell us what to do with the sequences that make it through the filters
    extractors = parser.add_mutually_exclusive_group()
    extractors.add_argument('--missing', action='store_true',
                            dest='include_missing', help="return fileseq-style sequences of missing frames")
    extractors.add_argument('--unique', action='store_true',
                            help='immediate nonzero return if multiple sequences exist')
    extractors.add_argument('--pad', action='store_true', dest='print_pad', help='width of frames numbers in sequence')
    extractors.add_argument('--first', action='store_true', dest='print_first',
                            help='print first number of sequence(s) on standard output')
    extractors.add_argument('--last', action='store_true', dest='print_last',
                            help='print last number of sequence(s) on standard output')
    parser.parse_args(argv[1:], namespace=tool)
    # tool.sequence_left_substrings.remove(frames_script)
    try:
        tool.summarize_frames()
        exit(0)
    except RuntimeError as error:
        print(f"error in frames command: {error}", file=stderr)
        exit(1)
