# Mosel interface to NEOS solvers using AMPL nl format

This provides a wrapper for [https://neos-server.org/neos/solvers/](NEOS Server)'s [https://neos-server.org/neos/xml-rpc.html](XML-RPC API), for use from Mosel.
It is based on the [official python client](https://github.com/NEOS-Server/PythonClient), but adds support for Mosel format and also stored credentials.

## Installation
The package is pip-installable from the git repository or from a local clone.

The package creates an executable/binary file `nemos`, which can be used as a solver in mosel models using the `nlsolv` model. The minimal code for using it in Mosel, assuming that the `nemos` binary is in the PATH, is:

## Usage

```
using nlsolv
setparam("nl_solver", "neos")
setparam("nl_path, "nemos")
setparam("nl_binary", false)
```

The last parameter is required because the XML format does not support model in binary format.

Solver-specific parameters can be passed to the solver using

```
setparam("nl_option", SOLVER_OPTIONS)
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
