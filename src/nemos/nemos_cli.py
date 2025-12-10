import os
import sys
import shutil
import argparse
from pathlib import Path
import keyring
#import getpass
import pwinput
import xmlrpc.client
from platformdirs import PlatformDirs
import json
import time
from collections import defaultdict

#import subprocess

import logging
#logging.basicConfig(format='%(levelname)s:%(filename)s:%(lineno)d: %(message)s', level=logging.DEBUG)
logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
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


def default_config() -> dict[str, dict]:
	'''
	get default values for the configuration file
	'''
	return {
		'neos': {
			'server': 'https://neos-server.org:3333', # URI for the XML-RPC API
			'category': 'milp',                       # problem category, as defined by NEOS
			'solver': 'FICO-Xpress',                  # solver, named as on NEOS
			'forbidden_solvers': ['Gurobi']           # solvers not available via XML-RPC (set not allowed in dict!)
		},
		'user': {
			'email': '',                  # email - required for NEOS runs
			'user': '',                   # username for NEOS account (optional)
			'keyring_id': 'NEOS Server',  # keyring id/name of the NEOS credentials
		}
	}


def config_file_path() -> Path:
	'''
	get path to the configuration file

	if the file does not exist, it will be created with default values
	'''
	app_name = 'neos4mosel'
	developer = 'mkaut'
	dirs = PlatformDirs(app_name, developer)
	cdir = dirs.user_config_path
	if not cdir.exists():
		Path.mkdir(cdir, parents=True)
	cfile = cdir / 'config.json'
	if not cfile.exists():
		config = default_config()
		with open(cfile, 'w') as f:
			json.dump(config, f, indent='\t')
		logger.info(f"Created config file `{config}`")
	return cfile


def get_config() -> dict:
	'''
	get the stored configuration
	'''
	cfile = config_file_path()
	assert cfile.is_file(), 'should be guaranteed at this point'
	with open(cfile, 'r') as f:
		config = json.load(f)
	return config


def get_neos_api(server_uri: str|None=None) -> xmlrpc.client.ServerProxy:
	'''
	connect to the NEOS XML-RPC API and return the connection object

	Args:
		server_uri: if given, use this URI instead of the one from the config file

	Returns:
		xmlrpc.client.ServerProxy object connected to NEOS
	'''
	config = get_config()
	c_neos = config.get('neos', None)
	assert c_neos, 'config file should always exist and have a "neos" section'

	server = server_uri or c_neos.get('server', None)
	if not server:
		logger.error("NEOS server URI not provided!")
		sys.exit(1)
	try:
		neos = xmlrpc.client.ServerProxy(server)
		neos.ping()
	except Exception as e:
		logger.error("Could not reach the NEOS server: ", e)
		sys.exit(1)
	return neos


def parse_neos_options(options_str: str) -> dict[str, str]:
	'''
	parse NEOS options string into a dictionary

	Args:
		options_str: string with options, e.g. "key1=val1 key2=val2"
		ignored_keys: set of keys to ignore

	All keys are converted to lower case.
		
	Returns:
		dictionary with option key-value pairs
	'''
	odict = {
		parts[0].strip().lower(): parts[1].strip()
		for o in options_str.split()
		if (parts := o.split('=', maxsplit=1)) and len(parts) == 2
	}
	return odict


def get_neos_config(odict: dict, neos: xmlrpc.client.ServerProxy) -> dict:
	'''
	get NEOS server configuration information

	Args:
		odict: dictionary with NEOS options
		neos: connected NEOS XML-RPC API object

	Returns:
		dictionary with NEOS configuration information
	'''
	config = get_config()
	c_neos = config['neos']
	c_user = config['user']

	# problem category
	if 'category' in odict:
		category = odict['category']
		neos_categories = neos.listCategories()  # returns a dict: name -> description
		if category not in neos_categories:
			logger.error(f'Unsupported problem category `{category}`')
			logger.info(f'Supported values are:')
			for cat, descr in neos_categories.items():
				logger.info(f"{cat}: {descr}")
			raise ValueError(f'Unsupported problem category `{category}`')
	else:
		category = c_neos['category']

	# solver
	if 'solver' in odict:
		solver = odict['solver']
		cat_solvers_list = neos.listSolversInCategory(category)  # item = 'solver:input'
		# set of solvers for the given category, supporting 'NL' format
		cat_solvers_nl = {s.split(':')[0] for s in cat_solvers_list if s.split(':')[1] == 'NL'}
		cat_solvers_nl -= set(c_neos['forbidden_solvers'])  # c_neos['forbidden_solvers'] is a list
		if solver not in cat_solvers_nl:
			logger.error(f"Solver {solver} is not supported for `{category}` problems with `NL` input.")
			logger.info("Supported solvers: ", cat_solvers_nl)
			raise ValueError(f"Unsupported solver `{solver}` for category `{category}`")
	else:
		solver = c_neos['solver']
	#
	neos_solvers = neos.listAllSolvers()
	if f'{category}:{solver}:NL' not in neos_solvers:
		logger.error(f"Specified NEOS solver `{category}:{solver}:NL` is not in the list!")
	logger.info(f"Specified NEOS solver = `{category}:{solver}:NL`")

	# priority (short or long)
	priority = odict.get('priority', 'short')
	
	# user authentication
	email = odict.get('email', c_user.get('email', ''))
	if email == '':
		raise Exception("NEOS requires email for problem submissions, please specify it.")
	#
	user = odict.get('user', c_user.get('user', ''))
	pwd = None
	# TODO: if it exists in odict, remove it from there and from `options`!
	if user != '':
		# try to get password
		pwd = keyring.get_password(c_user['keyring_id'], user)
		if pwd is None:
			logger.warning(f"No password found in the keyring for NEOS user {user}!")
			logger.warning(" -> submitting without authentication")
		else:
			logger.info(f"Submitting as NEOS user `{user}`.")

	return {
		'category': category,
		'solver': solver,
		'priority': priority,
		'email': email,
		'user': user,
		'pwd': pwd
	}
	

def neos_xml_string(odict: dict, nl_file: str|Path, config: dict) -> str:
	'''
	create the NEOS XML string for job submission

	Args:
		odict: dictionary with NEOS configuration options
		nl_file: path to the NL file to be solved
		config: dictionary with NEOS config information
	
	Returns:
		string with the NEOS XML job submission document
	'''
	# read the NL file
	with open(nl_file, 'r') as f:
		nl_mod_str = f.read()

	# options, one per line, excluding options meant for this script
	script_options = {'category', 'solver', 'priority', 'email', 'user'}
	neos_options = [f'{key}={val}' for key, val in odict.items() if key not in script_options]
	opt_str = '\n'.join(neos_options)

	neos_xml = f"""\
<document>
	<category>{config['category']}</category>
	<solver>{config['solver']}</solver>
	<inputMethod>NL</inputMethod>
	<priority>{config['priority']}</priority>
	<email>{config['email']}</email>
	<model><![CDATA[{nl_mod_str}]]></model>
	<options><![CDATA[{opt_str}]]></options>
	<comments><![CDATA[]]></comments>
</document>
"""


def solve_nl_file(nl_file: str|Path) -> None:
	'''
	Solve problem given by an .nl file on NEOS

	Solvers options are passed from Mosel via env. variable 'neos_options'!

	Communication using XML-RPC API
	- doc: https://neos-server.org/neos/xml-rpc.html

	Args:
		nl_file: path to the NL file to be solved
	'''

	nl_file = Path(nl_file)
	if not nl_file.is_file():
		raise FileNotFoundError(f"NL file `{nl_file}` not found!")
	# check that we have ASCII NL file (binary is not supported)
	# - NL file starts with 'g' for ASCII files and 'b' for binary files
	with open(nl_file, 'rb') as f:
		id_char = f.read(1).decode()  # reading binary -> have to decode
	match id_char:
		case 'b':
			raise ValueError(f"""
				NL file `{nl_file}` is in binary format, this is not supported!
				In Mosel, use `setparam("nl_binary", false)` to switch to ascii format.
			""")
		case 'g':
			pass  # this is what we want
		case _:
			logger.error(f"Could not detect format of NL file {nl_file} - expect problems!")
	# for testing - copy the NL file to the working dir
	#shutil.copy(nl_file, './tmp.nl')

	options_str = os.environ.get('neos_options', '')
	logging.debug(f"NEOS solver options = {options_str}")
	odict = parse_neos_options(options_str)
	logging.debug(f"NEOS options as dict: {odict}")

	## NEOS setup
	neos = get_neos_api(odict.get('server', None))
	config = get_neos_config(neos)
	neos_xml = neos_xml_string(odict, nl_file, config)

	# use for testing: save a copy of the XML file to the working dir
	#with open('tmp.xml', 'w') as f:
	#	f.write(neos_xml)

	## run the job - code based on https://github.com/NEOS-Server/PythonClient
	if config['pwd'] is not None:
		assert config['user'] != '', 'consistency check'
		job_id, job_pwd = neos.authenticatedSubmitJob(neos_xml, config['user'], config['pwd'])
	else:
		job_id, job_pwd = neos.submitJob(neos_xml)
	if job_id == 0:
		raise RuntimeError(f"NEOS job submission failed!")
	logger.info(f"Job submitted to NEOS; job no. = {job_id}, password = {job_pwd}")
	
	status = neos.getJobStatus(job_id, job_pwd)
	assert status in {'Waiting', 'Running', 'Done'}, 'check status'

	if config['priority'] == 'short':
		# only jobs sumbitted with 'short' priority (max 5 minutes)
		# report running results
		offset = 0
		print()
		while status != 'Done':
			time.sleep(1)
			# get running results, starting from a given offset
			# - returns the new offset, to be used for next call
			(msg, offset) = neos.getIntermediateResults(job_id, job_pwd, offset)
			print('\n', msg.data.decode())
			status = neos.getJobStatus(job_id, job_pwd)
	else:
		# long priority
		print('Job running with long priority -> no intermediate output')
		print('Please wait')
		t_min = 0
		while status != 'Done':
			time.sleep(60)
			t_min += 1
			print('.', end='\n' if t_min % 60 == 0 else '')
			status = neos.getJobStatus(job_id, job_pwd)
	# finished
	msg = neos.getFinalResults(job_id, job_pwd)
	print('\n', msg.data.decode())
	print()
	logger.info(f'NEOS completion code: {neos.getCompletionCode(job_id, job_pwd)}')

	## create the solution file
	# get the file from NEOS
	# - see documentation for a list of supported file names
	# - use the .data member to get decoded characters
	res = neos.getOutputFile(job_id, job_pwd, 'ampl.sol')
	sol_file = nl_file.with_suffix('.sol')
	with open(sol_file, 'wb') as f:
		f.write(res.data)
	

# ----------------------------------------------------------------------------

def non_mosel_call(args: argparse.Namespace) -> None:
	'''
	handle command line calls that are not from Mosel

	Args:
		args: parsed command line arguments
	'''
	config = get_config()
	assert 'neos' in config and 'user' in config, 'config file should always include "neos" and "user"'
	c_neos = config['neos']
	c_user = config['user']

	# NEOS information
	if args.neos_info:
		args.categories = True
		args.cat_solvers = True
		args.solver_cats = True
	if args.categories or args.cat_solvers or args.solver_cats:
		neos = get_neos_api()
		cat_list = neos.listCategories()     # returns dictionary cat-id -> description
		solver_comb = neos.listAllSolvers()  # returns list of 'category:solver:inputMethod
		forbidden_solvers = set(c_neos.get('forbidden_solvers', []))
		solver_comb_nl = [
			scl[:2]
			for sc in solver_comb
			if (scl := sc.split(':'))[2] == 'NL' and scl[1] not in forbidden_solvers
		]

		cat_solvers = defaultdict(list)
		solver_cats = defaultdict(list)
		for cat, solver in solver_comb_nl:
			cat_solvers[cat].append(solver)
			solver_cats[solver].append(cat)

		if args.categories:
			print(f"\nSupported problem categories:")
			for cat in cat_solvers.keys():
				print(f"{cat:<5s} : {cat_list[cat]}")
		if args.cat_solvers:
			print(f"\nSolvers per problem category:")
			for cat, solvers in cat_solvers.items():
				print(f"{cat:<5s} : {', '.join(sorted(solvers))}")
		if args.solver_cats:
			print("\nProblem categories per solver:")
			for solver, cats in solver_cats.items():
				print(f"{solver:<11s} : {', '.join(sorted(cats))}")
		sys.exit(0)

	# remaining options should be for credential management
	# - email and (optionally) NEOS username are stored in config
	# - password for the username is stored in the keyring
	email = c_user.get('email', '')
	user = c_user.get('user', '')
	if user != '':
		cred = keyring.get_credential(c_user['keyring_id'], user)
	else:
		cred = None

	save_config = False
	if args.show_email:
		if email != '':
			logger.info(f"Stored NEOS email is `{email}`")
		else:
			logger.info("No email stored for NEOS.")
	elif args.email:
		update = True
		if email != '':
			if args.email != email:
				logger.warning(f"There is already a stored email: `{email}`")
				ans = input('Overwrite it with the `{args.email}`? [Y/n] ')
				if ans not in {'', 'y', 'Y', 'j', 'J'}:
					update = False
			else:
				logger.info(f"This email is already in the config file.")
				update = False
		if update:
			c_user['email'] = args.email
			save_config = True

	if args.show_user:
		if user != '':
			logger.info(f"Stored NEOS username is `{email}`")
		else:
			logger.info("No username stored for NEOS.")
	elif args.set_cred:
		update = True
		if cred:
			logger.warning(f"There are already stored credentials for NEOS user `{cred.username}`!")
			ans = input('Delete them and enter new? [Y/n] ')
			if ans in {'', 'y', 'Y', 'j', 'J'}:
				keyring.delete_password(c_user['keyring_id'], cred.username)
			else:
				update = False
		if update:
			user = input('NEOS username: ')
			while True:
				pwd = pwinput.pwinput(prompt='NEOS password: ')
				if len(pwd) >= 9:  # possibly valid password - NEOS requires at least 9 characters
					break
			c_user['user'] = user
			save_config = True
			keyring.set_password(c_user['keyring_id'], user, pwd)
	elif args.del_cred:
		if not cred:
			logger.warning("No NEOS credentials found - nothing to delete")
			sys.exit(1)
		keyring.delete_password(c_user['keyring_id'], cred.username)
		c_user['user'] = ''
		save_config = True
	
	if save_config:
		with open(config_file_path(), 'w') as f:
			json.dump(config, f, indent='\t')


# ----------------------------------------------------------------------------
def main(argv=None):
	#log_levels = [v.lower() for k,v in logging._levelToName.items() if k > 0]
	termWidth = shutil.get_terminal_size()[0]
	helpFormatter = lambda prog: argparse.HelpFormatter(prog, max_help_position=30, width=termWidth)

	parser = argparse.ArgumentParser(prog='nemos', description='Mosel interface to NEOS solvers', formatter_class=helpFormatter)
	# positional arguments sent by Mosel: path to NL file and 'writesol'
	parser.add_argument('args', nargs='*', help='arguments Mosel sends to the solver')
	# keyword arguments sent by Mosel - hide from the help
	parser.add_argument('-s', action='store_true', help=argparse.SUPPRESS)
	parser.add_argument('-e', action='store_true', help=argparse.SUPPRESS)
	# credential management
	cred = parser.add_argument_group('credential management')
	cred.add_argument('--email', type=str, help='set email address for NEOS', metavar='EMAIL')
	cred.add_argument('--show-email', action='store_true', help='show stored NEOS email')
	cred.add_argument('--set-cred', action='store_true', help='input and store NEOS credentials')
	cred.add_argument('--show-user', action='store_true', help='show stored NEOS username')
	cred.add_argument('--del-cred', action='store_true', help='delete stored NEOS credentials')
	# NEOS solver information
	neos = parser.add_argument_group('NEOS solver information')
	neos.add_argument('--categories', action='store_true', help='list supported problem categories, with descriptions')
	neos.add_argument('--cat-solvers', action='store_true', help='list supported solvers, per problem category')
	neos.add_argument('--solver-cats', action='store_true', help='list supported problem categories, per solver')
	neos.add_argument('--neos-info', action='store_true', help='show all the lists above')

	# prepare command line arguments for parse_args
	# - accepts None - uses sys.argv[1:] in that case
	# - otherwise, argv should be a list of strings
	if isinstance(argv, str):
		argv = argv.split()
	args = parser.parse_args(argv)

	if len(args.args) == 0:
		# not a Mosel call
		non_mosel_call(args)
		return

	# assuming script was called from Mosel
	if not(args.s and args.e):
		logger.warning(f"Unexpected format of Mosel solver arguments: {argv}")
	nl_file = args.args[0]
	solve_nl_file(nl_file)


if __name__ == "__main__":
	main()
