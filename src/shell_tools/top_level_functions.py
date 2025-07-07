
from sys import argv, stderr
import argparse

from .frames import FRAMES_VERSION, FramesTool

def frames_cmd_top_level():
    tool = FramesTool()
    # frames_script = argv[0]
    parser = argparse.ArgumentParser(prog='frames')
    parser.add_argument('--version', action='version', version=f"%(prog)s {FRAMES_VERSION}")
    # These act as filters for the set of sequences to examine
    parser.add_argument('--sequences', action=argparse.BooleanOptionalAction, default=True,
                        dest='include_sequences', help='include files recognizably consecutive clips or frames')
    parser.add_argument('--gaps', action=argparse.BooleanOptionalAction, default=False,
                        dest='include_gaps', help='include files between runs of recognizably clips or frames')
    parser.add_argument('--debris', action=argparse.BooleanOptionalAction, default=False,
                        dest='include_debris', help='include files not recognizably clips or frames')
    parser.add_argument('dir', type=str)
    parser.add_argument('sequence_left_substrings', metavar='substr', type=str, nargs='*',
                        help='left substring filter for sequence(s)')
    # These tell us what to do with the sequences that make it through the filters
    extractors = parser.add_mutually_exclusive_group()
    extractors.add_argument('--uniqueness_check', action='store_true', dest='uniqueness_check',
                            help='immediate nonzero return if multiple sequences exist')
    extractors.add_argument('--frame_field_width', action='store_true',
                            dest='print_frame_field_width',
                            help='width of frames numbers in sequence')
    extractors.add_argument('--first', action='store_true', dest='print_first',
                            help='print first number of sequence(s) on standard output')
    extractors.add_argument('--last', action='store_true', dest='print_last',
                            help='print last number of sequence(s) on standard output')
    parser.parse_args(argv[1:], namespace=tool)
    try:
        success: bool = tool.run()
        print('done')
        exit(0) if success else exit(0)
    except RuntimeError as error:
        print(f"error in frames command: {error}", file=stderr)
        exit(1)
