========
Saturnin
========

Saturnin is an implementation of Firebird Butler platform for Python.

.. important::

   For best experience with Saturnin console and other tools, we recommend to use terminal
   with good support for ANSI escape sequences. On Windows platform, we recommend to use
   `Windows Terminal`_.

Installation
************

You will need Python v3.8 or later to install Saturnin.

For regular deployments, we recommend installing using the pipx_ tool, which installs into
a separate virtual Python environment and exposes all executable commands in the search path.

::

  > pip install pipx
  > pipx install saturnin

If you want to develop your own services using the Saturnin SDK, we recommend that you
first create a separate virtual environment into which you install Saturnin in the usual
way with the pip_ tool.

Initialization
**************

Saturnin uses a number of files and directories whose location in the file system corresponds
to the standards for the platform on which it is installed. This basic directory placement
scheme can be changed by using the `SATURNIN_HOME` environment variable, which sets the root
of the other directory locations. Alternatively, you can create a `"home"` subdirectory in
the root directory of the virtual environment in which Saturnin is isolated.

.. important::

   Because on Linux or MacOS the default location of some directories may require higher
   than normal access rights, we recommend that you always use the home directory setting
   on these platforms.

.. tip::

   To set the home directory in the virtual environment (recommended when installing with
   pipx_), use the command::

     > saturnin create home

The next step is to initialize the Saturnin installation with the command::

   > saturnin initialize

Saturnin console
****************

The `saturnin` tool is used to manage the Saturnin platform installation. It can be operated
in two modes:

- **Single command (direct) mode.** The required command and parameters are entered directly on
  the command line, and after the command is executed, the tool is terminated.

- **Interactive console mode** activated by running the tool without additional parameters.
  The interactive console offers an enhanced command line with persistent command history,
  command and parameter completion, and interactive help.

.. note::

   The command set available in console mode differs from command set available in direct mode,
   as some commands (typically those required to run only once or not very often like initialize
   or create home) are available only in direct mode.

For normal work, we recommend using the interactive console mode. In the following sections,
all the commands described are entered in the interactive console.

Installing services
*******************

Immediately after installation, Saturnin does not provide any Butler services. These
services need to be installed separately. Although you can install service packages with
the standard pip utility, we recommend that you use saturnin's `install package`,
`uninstall package`, and `pip` commands to install, uninstall, or manage service packages,
as these commands also update the necessary registries that Saturnin uses to work with
Butler services and Saturnin applications.

.. note::

   If necessary, the command: `update registry` can be used to update the registries.

To install package with Saturnin core services, use command::

   > install package saturnin-core

Using Firebird services
***********************

To use Butler services that work with Firebird server, you need to create (and update)
a configuration file for the firebird driver using the commands::

   > create config firebird
   > edit config firebird

Saturnin recipes
****************

Recipes are Saturnin-specific configuration files with instructions for running Butler
services built for Saturnin. Recipes can be created with the create recipe command, which
creates a recipe template that typically needs to be modified further (because it only
contains default values). Recipes created independently (e.g. by a solution supplier or
provided by installed Saturnin application) must be installed with the `install recipe` command.

Created or installed recipes can be run with the `run recipe-name` command. You can get
a list of recipes that can be started with the `list recipes` command.

For more information, see the `Usage Guide`_.

.. _pip: https://pypi.org/project/pip/
.. _pipx: https://pypa.github.io/pipx/
.. _Usage Guide: https://saturnin.readthedocs.io/en/latest/usage-guide.html
.. _Windows Terminal: https://aka.ms/terminal
