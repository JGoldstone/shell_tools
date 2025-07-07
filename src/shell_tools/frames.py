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
from abc import abstractmethod, ABC
from copy import copy
from sys import argv, exit, stderr
import argparse
from enum import Flag, auto

from fileseq import findSequencesOnDisk, FileSequence, FrameSet

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
KNOWN_IMAGE_ESSENCE_CONTAINER_EXTENSIONS = (
    '.mov', '.mxf',
    '.ari', '.dpx', '.exr', '.tif', '.tiff', '.png', '.cin', '.heif')

def has_container_extension(seq: FileSequence) -> bool:
    return seq.extension() in KNOWN_IMAGE_ESSENCE_CONTAINER_EXTENSIONS

class SequenceVariant(Flag):
    RUN = auto()
    GAP = auto()


class Content(ABC):
    def __init__(self, seq: FileSequence, is_container: bool = False):
        self.seq = seq
        self.is_container = is_container

    @abstractmethod
    def is_sequence_variant(self, variant: SequenceVariant) -> bool:
        raise NotImplementedError("No concrete is_sequence method provided")

    @abstractmethod
    def bounds_and_count_widths(self) -> tuple[int, int, int]:
        raise NotImplementedError("No concrete bounds_and_count_widths method provided")

    def nuke_format_spec(self, frame_number_width: int) -> str:
        frame_spec: str = f"%0{frame_number_width}d" if frame_number_width != 0 else ''
        return (f"{self.seq.basename()}"
                f"{frame_spec}"
                f"{self.seq.extension()}")

    @abstractmethod
    def formatted_str(self,
                      start_width: int,
                      end_width: int,
                      count_width: int) -> str:
        raise NotImplementedError("No concrete formatted_str method provided")


class SequencedFrames(Content):
    def __init__(self,
                 seq: FileSequence,
                 variant: SequenceVariant):
        super(SequencedFrames, self).__init__(seq=seq, is_container=has_container_extension(seq))
        self.variant = variant

    def start_frame(self) -> int:
        return self.seq.start()

    def bounds(self) -> tuple[int, int]:
        start: int = self.seq.frameSet().start()
        end: int = self.seq.frameSet().end()
        return start, end

    def is_sequence_variant(self, variant: SequenceVariant) -> bool:
        return True if variant == SequenceVariant.RUN else False

    def bounds_and_count_widths(self) -> tuple[int, int, int]:
        start, end = self.bounds()
        start_width = len(f"{start}")
        end_width = len(f"{end}")
        count_width = len(f"{1+end-start}")
        return start_width, end_width, count_width

    def formatted_str(self,
                      start_width: int,
                      end_width: int,
                      count_width: int) -> str:
        start, end = self.bounds()
        start_color: str = BlenderColors.OKGREEN if self.variant == SequenceVariant.RUN else BlenderColors.FAIL
        end_color: str = BlenderColors.ENDC
        return (f"{start:>{start_width}}-{end:<{end_width}}"
                f"| {1 + end - start:<{count_width}} "
                f"{start_color}"
                f"{self.nuke_format_spec(end_width-1)}"
                f"{end_color}")

    def __str__(self):
        """left-justified range, count, filename"""
        start_width, end_width, count_width = self.bounds_and_count_widths()
        return self.formatted_str(start_width, end_width, count_width)

    def str_in_column_context(self, start_width: int, end_width: int,
                              count_width: int) -> str:
        return self.formatted_str(start_width, end_width, count_width)

    def __repr__(self):
        return f"FrameSequence('{self.seq.__repr__()}')"


class UnsequencedFrame(Content):
    def __init__(self, seq: FileSequence):
        super(UnsequencedFrame, self).__init__(seq=seq, is_container=has_container_extension(seq))

    def is_sequence_variant(self, variant: SequenceVariant) -> bool:
        return True if variant == SequenceVariant.GAP else False

    def bounds_and_count_widths(self) -> tuple[int, int, int]:
        frame_width = len(str(self.seq.frameSet()))
        return frame_width, frame_width, frame_width

    def formatted_str(self, start_width: int, end_width: int,
                      count_width: int) -> str:
        # "sssss - eeeeeeee  cccccccc:  foo.tiff"
        left_margin = start_width + 1 + end_width
        start_color: str = BlenderColors.OKBLUE
        end_color: str = BlenderColors.ENDC
        return (f"{' ' * left_margin}  {' ':>{count_width}} "
                f"{start_color}"
                f"{self.nuke_format_spec(0)}"
                f"{end_color}")

    def __str__(self):
        return self.seq.basename


class Debris(UnsequencedFrame):
    def __init__(self, seq: FileSequence):
        super(UnsequencedFrame, self).__init__(seq=seq)

    def is_sequence_variant(self, _) -> bool:
        return False

    def bounds_and_count_widths(self) -> tuple[int, int, int]:
        return 0, 0, 0

    def formatted_str(self, start_width: int, end_width: int,
                      count_width: int) -> str:
        # "sssss - eeeeeeee  cccccccc:  foo.tiff"
        left_margin = start_width + 1 + end_width + 2 + count_width
        start_color: str = BlenderColors.WARNING
        end_color: str = BlenderColors.ENDC
        return (f"{' ' * left_margin} "
                f"{start_color}"
                f"{self.nuke_format_spec(0)}"
                f"{end_color}")


class ContentFormatter:
    """Hold all files or a subset of files in a directory"""
    def __init__(self, content: list[Content]):
        self.content = content

    def col_widths(self):
        widths = [c.bounds_and_count_widths() for c in self.content]
        start_widths, end_widths, count_widths = zip(*widths)
        max_start_width = max(start_widths)
        max_end_width = max(end_widths)
        max_count_width = max(count_widths)
        return max_start_width, max_end_width, max_count_width

    def summary_lines(self):
        max_start_width, max_end_width, max_count_width = self.col_widths()
        return [c.formatted_str(max_start_width, max_end_width, max_count_width)
                for c in self.content]


class FramesTool(object):

    def __init__(self):
        # These are here to make PyCharm shut up about unresolved attribute references; parse_args would have set them.
        self.dir: str | None = None
        self.include_sequences: bool = True
        self.include_gaps: bool = True
        self.include_debris: bool = True
        self.sequence_left_substrings: tuple[str, ...] = tuple()
        # These are mutually exclusive (only none or one can be specified)
        self.uniqueness_check = False
        self.print_frame_field_width = False
        self.print_first = False
        self.print_last = False
        # This is what we build up
        self._content: list[Content] = []

    @staticmethod
    def copy_seq(seq: FileSequence, frames: str) -> FileSequence:
        copied_seq = copy(seq)
        copied_seq.setFrameSet(FrameSet(frames))
        return copied_seq

    @staticmethod
    def unwrapped_sequences(seq: FileSequence) -> list[SequencedFrames]:
        run_frames: list[str] = seq.frameSet().frange.split(',')
        if len(run_frames) == 1 and run_frames[0] == '':
            run_frames = []
        gap_frames: list[str] = seq.frameSet().invertedFrameRange().split(',')
        if gap_frames == ['']:
            gap_frames = []
        run_seqs: list[SequencedFrames] = [SequencedFrames(seq=FramesTool.copy_seq(seq, r),
                                                           variant=SequenceVariant.RUN)
                                           for r in run_frames]
        gap_seqs: list[SequencedFrames] = [SequencedFrames(seq=FramesTool.copy_seq(seq, r),
                                                           variant=SequenceVariant.GAP)
                                           for r in gap_frames]
        seqs = sorted(run_seqs + gap_seqs, key=lambda x: x.seq.start())
        return seqs


    def load_from_dir(self) -> list[Content]:
        seqs: list[FileSequence] = sorted(findSequencesOnDisk(self.dir), key=FileSequence.basename)
        content: list[Content] = []
        for seq in seqs:
            if seq.frameSet():
                content += FramesTool.unwrapped_sequences(seq)
            elif seq.extension() in KNOWN_IMAGE_ESSENCE_CONTAINER_EXTENSIONS:
                content += [UnsequencedFrame(seq)]
            else:
                content += [Debris(seq)]
        return content

    def keep(self, content: Content) -> bool:
        if self.sequence_left_substrings:
            return not any([content.seq.basename().startswith(s)
                            for s in self.sequence_left_substrings])
        if content.is_sequence_variant(SequenceVariant.RUN) and not self.include_sequences:
            return False
        if content.is_sequence_variant(SequenceVariant.GAP) and not self.include_gaps:
            return False
        if not content.is_container and not self.include_debris:
            return False
        return True

    def print_formatted_contents(self):
        formatter = ContentFormatter(self._content)
        for line in formatter.summary_lines():
            print(line)


    def run(self) -> bool:
        self._content: list[Content] = self.load_from_dir()
        self._content = [c for c in self._content if self.keep(c)]
        if len(self._content) == 1:
            frame_set = self._content[0].seq.frameSet()
            if self.print_first:
                print(frame_set.split('-')[0])
                return True
            if self.print_last:
                print(frame_set.split('-')[1])
                return True
            if self.print_frame_field_width:
                _, end_width, _ = self._content[0].bounds_and_count_widths()
                print(end_width)
            return True
        elif self.uniqueness_check:
            return False
        else:
            self.print_formatted_contents()
            return True
#
#
# def frames_cmd_top_level():
#     tool = FramesTool()
#     # frames_script = argv[0]
#     parser = argparse.ArgumentParser(prog='frames')
#     parser.add_argument('--version', action='version', version=f"%(prog)s {FRAMES_VERSION}")
#     # These act as filters for the set of sequences to examine
#     parser.add_argument('--sequences', action=argparse.BooleanOptionalAction, default=True,
#                         dest='include_sequences', help='include files recognizably consecutive clips or frames')
#     parser.add_argument('--gaps', action=argparse.BooleanOptionalAction, default=False,
#                         dest='include_gaps', help='include files between runs of recognizably clips or frames')
#     parser.add_argument('--debris', action=argparse.BooleanOptionalAction, default=False,
#                         dest='include_debris', help='include files not recognizably clips or frames')
#     parser.add_argument('dir', type=str)
#     parser.add_argument('sequence_left_substrings', metavar='substr', type=str, nargs='*',
#                         help='left substring filter for sequence(s)')
#     # These tell us what to do with the sequences that make it through the filters
#     extractors = parser.add_mutually_exclusive_group()
#     extractors.add_argument('--uniqueness_check', action='store_true', dest='uniqueness_check',
#                             help='immediate nonzero return if multiple sequences exist')
#     extractors.add_argument('--frame_field_width', action='store_true',
#                             dest='print_frame_field_width',
#                             help='width of frames numbers in sequence')
#     extractors.add_argument('--first', action='store_true', dest='print_first',
#                             help='print first number of sequence(s) on standard output')
#     extractors.add_argument('--last', action='store_true', dest='print_last',
#                             help='print last number of sequence(s) on standard output')
#     parser.parse_args(argv[1:], namespace=tool)
#     try:
#         success: bool = tool.run()
#         print('done')
#         exit(0) if success else exit(0)
#     except RuntimeError as error:
#         print(f"error in frames command: {error}", file=stderr)
#         exit(1)
#     finally:
#         exit(0)

