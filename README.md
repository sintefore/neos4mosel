# Mosel interface to NEOS solvers using AMPL nl format

This provides a wrapper for [https://neos-server.org/neos/solvers/](NEOS Server)'s [https://neos-server.org/neos/xml-rpc.html](XML-RPC API), for use from Mosel.
It is based on the [official python client](https://github.com/NEOS-Server/PythonClient), but adds support for Mosel format and also stored credentials.

## Installation
The package is pip-installable from its gitlab repository or from a local clone.

### Pip-install from gitlab

There are two options to install directly from the [gitlab repository](https://gitlab.sintef.no/mkaut/codes/neos4mosel).
The first one is using HTTPs and requires a token registerd at gitlab, while the other is using SSH and requires a registered certificate instead:

```console
pip install git+https://gitlab.sintef.no/mkaut/codes/neos4mosel.git

pip install git+ssh://git@gitlab.sintef.no/mkaut/codes/neos4mosel.git
```

## Usage

The package creates an executable/binary file `nemos`, which can be used as a solver in mosel models using the `nlsolv` model. The minimal code for using it in Mosel, assuming that the `nemos` binary is in the PATH, is:

```
uses nlsolv
setparam("NL_solver", "neos")       ! solver identifier
setparam("NL_solverpath", "nemos")  ! name of the solver binary - must be in PATH
setparam("NL_binary", false)        ! NEOS XML does not work with the default binary format
```

The last parameter is required because the XML format does not support model in binary format.
Also note that names of Mosel parameters are not case sensitive, so "nl_solver" etc. works as well.

Solver-specific parameters can be passed to the solver using

```
setparam("NL_options", SOLVER_OPTIONS)
```

where `SOLVEROPTIONS` is a space-separated list of key=value entries.
In addition to the solver parameters, the list can include the following parameters for the `nemos` binary:

- `category` - NEOS problem category, defaults to `milp`
- `solver` - NEOS solver, defaults to `FICO-Xpress`
- `priority` - NEOS job priority
	- `short` (default) limits jobs to 5 minutes, but start immediately and reports progress
	- `long` allows jobs up to 24 hours, but they can be put in a queue
- `email` - email to use for the job
	- NEOS requires email for each running job
	- it is also possible to register the email, see below
- `user` - NEOS username (optional)
	- must belong to credentials registered in system keyring

Run `nemos --neos-info` to get a list of supported solvers and problem categories.
Note that this includes only combinations usable from Mosel, i.e., supporting the AMPL NL input.
Moreover, the list does _not_ include Gurobi, since this cannot be used via the XML-RPC API.


### Authentication

Each NEOS job must be provided with an email address.
In addition, it is possible to make a free account on NEOS, providing access to results of jobs rund under this account.

The `nemos` binary allows registering both email and the NEOS credentials, to simplify the work.
The username is stored in the package's config file, while the password is stored in system's keyring.

For email, it provides commands for registering an email and then reviewing it:

```console
nemos --email name@server
nemos --show-email
```

The syntax is slightly different for NEOS credentials, since we don't want to show password in clear text:

```console
nemos --set-cred
nemos --show-user
nemos --del-cred
```

The first command asks for username and password, while the last command removes the password from the keyring and the username from the config file.


### Stand-alone usage

While `nemos` is meant to be called from Mosel, it can solve a standalone NL file as well.
For this, simply run

```
nemos problem.nl
```

and there should appear `problem.sol` in the same directory as `problem.nl`.
Solver options can be provided using environmental variable `neos_options`.

To avoid warning about wrong syntax of input arguments, add dummy options `-s -e` to the call.
