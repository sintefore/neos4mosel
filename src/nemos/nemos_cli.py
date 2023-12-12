import os
import sys
import shutil
import argparse
from pathlib import Path

import subprocess

import logging
logger = logging.getLogger(__name__)

# if 'rich' is installed, use it to for misc. enhancements:
try:
	from rich import print    # adds highlighting to normal print - see https://rich.readthedocs.io/en/stable/introduction.html#quick-start
	from rich import inspect  # object inspection in interactive session - see https://rich.readthedocs.io/en/stable/introduction.html#rich-inspect
	from rich.logging import RichHandler  # handler that adds some colour to logging - see https://rich.readthedocs.io/en/stable/logging.html
	# this will do detailed reporting of _unhandled_ exceptions
	from rich.traceback import install
	install(show_locals=True)
	_has_rich = True
except:
	_has_rich = False


# ----------------------------------------------------------------------------

def main(argv=None):
	termWidth = shutil.get_terminal_size()[0]
	helpFormatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=30, width=termWidth)

	#log_levels = [v.lower() for k,v in logging._levelToName.items() if k > 0]

	# top-level parser, only to decide the command
	# - see https://docs.python.org/3/library/argparse.html#sub-commands for more info
	parser = argparse.ArgumentParser(prog='nemos', description='Mosel interface to NEOS solvers', formatter_class=helpFormatter)
	parser.add_argument('args', nargs='*', help='arguments Mosel sends to the solver')
	parser.add_argument('-s', action='store_true', help=argparse.SUPPRESS)
	parser.add_argument('-e', action='store_true', help=argparse.SUPPRESS)
	parser.add_argument('--set-email', type=str, help='email address for NEOS', metavar='EMAIL')
	parser.add_argument('--set-cred', action='store_true', help='set and store credentials for NEOS')
	parser.add_argument('--show-email', action='store_true', help='show stored NEOS email')

	# prepare command line arguments for parse_args
	# - accepts None - uses sys.argv[1:] in that case
	# - otherwise, argv should be a list of strings
	if isinstance(argv, str):
		argv = argv.split()
	args = parser.parse_args(argv)

	print(f"{args = }")

if __name__ == "__main__":
	main()
