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
KNOWN_IMAGE_ESSENCE_CONTAINERS = ('.mov', '.mxf', '.ari', '.dpx', '.exr')


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
        pass
        # These are here to make PyCharm shut up about unresolved attribute references; parse_args would have set them.
        # self.sequence_left_substrings = []
        # # self.include_sequences = False
        # self.include_debris = False
        # self.inverse = False
        # self.unique = False
        # self.print_pad = False
        # self.print_first = False
        # self.print_last = False

    def _find_sequences_and_debris(self):
        seqs = findSequencesOnDisk(str(Path.cwd()))
        if len(self.sequence_left_substrings) > 0:
            seqs = {s for s in seqs if s.basename().startswith(self.sequence_left_substrings)}
        self._image_essence_sequences = {s for s in seqs if s.extension() in KNOWN_IMAGE_ESSENCE_CONTAINERS}
        self._debris = {s.basename() for s in seqs if s not in self._image_essence_sequences}

    def _sub_seq_frame_desc(self, sub_seq, present, max_zfill):
        start_digits = f"{sub_seq[0]}"
        end_digits = f"{sub_seq[1]}"
        if start_digits == end_digits:
            total_field_width = max_zfill + 1 + max_zfill
            leading_pad = f"{' '*((total_field_width - len(start_digits)) // 2)}"
            trailing_pad = f"{' '*(total_field_width - (len(leading_pad) + len(start_digits)))}"
            frames = f"{start_digits}"
        else:
            leading_pad = f"{' ' * (max_zfill - len(start_digits))}"
            trailing_pad = f"{' '*(max_zfill - len(end_digits))}"
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
                    sub_seq_count_leading_pad = f"{' '*(max_subseq_count_width - sub_seq_count_width)}"
                    count = f"{sub_seq_count_leading_pad}({sub_seq_count}) "
                    seq_desc = seq_in_nuke_style if is_first_sub_seq else f'{" "*(len(seq_in_nuke_style)//2)}"'
                    print(f"{sub_seq_frames} {count}{seq_desc}")
                present = not present
                is_first_sub_seq = False
        if self.include_debris:
            for thing in self._debris:
                frame_range_padding = f"{' '*(max_zfill + 1 + max_zfill)}"
                count_padding = f"{' '*(1 + 1 + max_subseq_count_width + 1)}"
                print(f"{frame_range_padding}{count_padding} {BlenderColors.WARNING}{thing}{BlenderColors.ENDC}")


if __name__ == '__main__':
    tool = FramesTool()
    frames_script = argv[0]
    parser = argparse.ArgumentParser(prog='frames')
    parser.add_argument('--version', action='version', version=f"%(prog)s {FRAMES_VERSION}")
    # These act as filters for the set of sequences to examine
    parser.add_argument('--sequences', action='store_false', dest='include_sequences',
                        help='limit to files recognizably clips or frames')
    parser.add_argument('--debris', action='store_true', dest='include_debris',
                        help='limit to files not recognizably clips or frames')
    parser.add_argument('sequence_left_substrings', metavar='substr', type=str, nargs='*',
                        help='left substring filter for sequence(s)')
    # These tell us what to do with the sequences that make it through the filters
    extractors = parser.add_mutually_exclusive_group()
    extractors.add_argument('--missing', action='store_true', dest='include_missing',
                            help="return fileseq-style sequences of missing frames")
    extractors.add_argument('--unique', action='store_true',
                            help='immediate nonzero return if multiple sequences exist')
    extractors.add_argument('--pad', action='store_true', dest='print_pad', help='width of frames numbers in sequence')
    extractors.add_argument('--first', action='store_true', dest='print_first',
                            help='print first number of sequence(s) on standard output')
    extractors.add_argument('--last', action='store_true', dest='print_last',
                            help='print last number of sequence(s) on standard output')
    parser.parse_args(argv, namespace=tool)
    tool.sequence_left_substrings.remove(frames_script)
    try:
        tool.summarize_frames()
        exit(0)
    except RuntimeError as error:
        print(f"error in frames command: {error}", file=stderr)
        exit(1)
