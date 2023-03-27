
===========
Usage Guide
===========

The Saturnin package contains the basic runtime environment for `Firebird Butler services`_,
and forms the basis of the Python implementation of the Firebird Butler platform. The Butler
services themselves are not part of the base distribution, and packages with these services
must be installed separately. The basic set of services for Saturnin is distributed as
`saturnin-core`_ package.

The basic concepts on which Saturnin is built are described in `introduction to Firebird Butler`_.

For instructions how to install and setup Saturnin on your machine, see the
:doc:`Getting Started <getting-started>` guide.

Basic Architecture
==================

Saturnin can be divided into two main parts:

1. Basic modules for implementing Butler services in Python. This documentation provides
   only the :doc:`reference guide <reference>` for these modules. Instructions (and examples)
   for their use for creating Butler services for the Saturnin platform are part of the documentation
   for the `saturnin-sdk`_ package.
2. Tools for managing and running Butler services, and their composition into functional
   units. This user guide describes this part of the platform.

Butler Services
***************

Saturnin currently supports two types of Butler services:

1. **Standard Butler services.** These services use the FBSP_ protocol and work in client/server
   mode.
2. **Microservices.** These are primarily data processing services that use the FBDP_ protocol
   for communication within the data processing pipeline.

Butler services are implemented as Python classes in Saturnin. Service properties are
defined by a standard `.ServiceDescriptor` structure, which is registered during installation
using a standard entry point in `saturnin.service` group.

Service containers
******************

Because services are classes, they cannot be invoked directly. Saturnin provides special
containers / utilities for running services:

1. The `saturnin-bundle` tool provides an environment for running multiple services in
   separate threads. It can be used both for running related services (eg data processing
   pipelines) and for centralized operation of unrelated services.

2. The `saturnin-service` tool allows you to run only one service, but allows that service
   to run either in the main process thread or in a separate thread.

Service containers can also be run as daemons using the `saturnin-daemon` tool.

Any number of such service container processes can be started. The definition of parameters
of the runtime environment, the list of services to be executed and their configuration is
described in a special configuration file called Saturnin **recipe.**

Although it is possible to use these containers directly, Saturnin offers a much more 
convenient way for normal operation in the form of integrating recipes directly into 
the `saturnin console`_.

Saturnin recipes
****************

Saturnin uses configuration objects based on `firebird.base.config` module. These objects
could be initialized from / persisted to text files with classic .INI file structure.
Single configuration file could be used to initialize multiple configuration objects, and
Saturnin always uses `~.configparser.ConfigParser` with extended interpolation support to 
process these files.

.. code-block:: cfg

   ; this is a comment
   # this is also comment
   [section]
   parameter1 = value
   parameter2 =
     this is
     multiline
     value

   [another.section]
   parameter1 = value
   ; interpolation for value in the same section
   parameter2 = ${parameter1}
   ; interpolation for value in different section
   parameter3 = ${section:parameter1}

Saturnin recipes contain configuration information that describes:

1. Recipe parameters (`.SaturninRecipe`)
2. Container configuration. Used section(s), their name(s) and structure depend on used container.
   By default:
   
   * the `saturnin-bundle` container uses a "bundle" section with a `.ServiceBundleConfig` structure 
     that refers to the configuration sections of individual components. 
   
   * the `saturnin-service` container uses a "service" section with a `.ServiceExecConfig` structure. 
     The same section is then used to configure the running component.

3. Configuration of components (sections used to set up particular component configuration objects)
4. Optional `.logging` configuration
5. Optional `~firebird.base.trace` configuration

Here is a sample recipe to print Firebird log on screen using two Saturnin microservices:

.. code-block:: cfg

   ; 1. Recipe parameters
   [saturnin.recipe]                                                                                                      
   recipe_type = bundle                                                                                                   
   execution_mode = normal                                                                                                
   description = Simple recipe that print log from local Firebird server.                                           

   ; 2. Bundle content                                                                                              
   [bundle]                                                                                                               
   agents = from-server, writer                                                                    

   ; Helper section to centralize definition of shared parameters
   [pipe]
   name = pipe-1
   address = inproc://pipe-1

   ; 3. Confguration of components                                                                                                      
   [from-server]                                                                                                          
   agent = 212657dc-2618-5f4b-a8f5-d8d42e99fe7e                                                                           
   pipe = ${pipe:name}                                                                                                      
   pipe_address = ${pipe:address}                                                                                        
   pipe_mode = bind                                                                                                       
   pipe_format = text/plain;charset=utf-8                                                                                 
   server = local                                                                                                         

   [writer]                                                                                                               
   agent = 4e606fdf-3fa9-5d18-a714-9448a8085aab                                                                           
   pipe = ${pipe:name}
   pipe_address = ${pipe:address}                                                                                        
   pipe_mode = connect                                                                                                    
   pipe_format = text/plain;charset=utf-8                                                                                 
   filename = stdout                                                                                                      
   file_format = text/plain;charset=utf-8                                                                                 
   file_mode = write   

Saturnin applications
*********************

Recipes are primarily clearly defined and static. The Saturnin application mechanism is 
available for the implementation of dynamic recipes. These are specific user-defined 
commands for the saturnin console that can be associated with specific recipes. Instructions 
for creating applications, including examples, can be found in the `Saturnin SDK`_ documentation.

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

Saturnin environment
====================

Saturnin uses a number of files and directories whose location in the file system corresponds
to the standards for the platform on which it is installed. This basic directory placement
scheme can be changed by using the `SATURNIN_HOME` environment variable, which sets the root
of the other directory locations. Alternatively, you can create a `"home"` subdirectory in
the root directory of the virtual environment in which Saturnin is isolated.

.. important::

   Because on Linux or MacOS the default location of some directories may require higher
   than normal access rights, we recommend that you always use the home directory setting
   on these platforms.

To set the home directory in the virtual environment (recommended when installing with
pipx_), use the command::

   > saturnin create home

Saturnin directories and configuration files are created with::

   > saturnin initialize

.. note::

   It is safe to run `initialize` on an already initialized environment because existing 
   directories or configuration files are not overwritten by default. 
   
   Run `saturnin initialize --help` for a complete description of the command and available options.

Directories
***********

`saturnin console`_  provides `list directories` command, that prints all directories used by 
Saturnin. An existence check is performed, and status of each directory is indicated with `✔` (exists) 
and `✖` (missing) marks.
   
   ::

      > list directories
      ╭─ Saturnin directories ──────────────────────────────────────────────────────────────────────────────╮
      │ SATURNIN_HOME is set to     : /home/saturnin/home                                                   │
      │ Saturnin configuration      ✔ /home/saturnin/home/config                                            │
      │ Saturnin data               ✔ /home/saturnin/home/data                                              │
      │ Run-time data               ✔ /home/saturnin/home/run_data                                          │
      │ Log files                   ✔ /home/saturnin/home/logs                                              │
      │ Temporary files             ✔ /var/tmp/saturnin                                                     │
      │ Cache                       ✔ /home/saturnin/home/cache                                             │
      │ User-specific configuration ✔ /home/user/.config/saturnin                                           │
      │ User-specific data          ✔ /home/user/.local/share/saturnin                                      │
      │ PID files                   ✔ /home/saturnin/home/run_data/pids                                     │
      │ Recipes                     ✔ /home/saturnin/home/data/recipes                                      │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

If any directory is listed as missing, it's necessary to run `saturnin initialize` command.

Configuration files
*******************

The `saturnin console`_ provides several configuration-related commands:

1. Command `list configs` prints all configuration files used by Saturnin. An existence check is performed, 
   and status of each file is indicated with `✔` (exists) and `✖` (missing) marks.
   
   ::

      > list configs
      ╭─ Configuration files ───────────────────────────────────────────────────────────────────────────────╮
      │ Main configuration     ✔ /home/job/python/projects/saturnin/home/config/saturnin.conf               │
      │ User configuration     ✔ /home/pcisar/.config/saturnin/saturnin.conf                                │
      │ Console theme          ✔ /home/job/python/projects/saturnin/home/config/theme.conf                  │
      │ Firebird configuration ✔ /home/job/python/projects/saturnin/home/config/firebird.conf               │
      │ Logging configuration  ✔ /home/job/python/projects/saturnin/home/config/logging.conf                │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

2. Command `create config` to create particular configuration file with default content.

   While all **required** configuration files are created by `saturnin initialize` command, optional files could 
   (or must) be created with this command. This command could be also used to quickly reset any configuration
   file to default values.

   Usage:: 
   
      > create config [OPTIONS] {main|user|firebird|logging|theme} 

      Creates configuration file with default content.                                                       
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    config_file      {main|user|firebird|logging|theme}     Configuration file to be created       │
      │                                                              [default: None]                        │
      │                                                              [required]                             │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --new-config          Create configuration file even if it already exist.                           │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   .. important::

      The Firebird configuration file is optional as Saturnin is not stricly bound to Firebird RDBMS, and 
      this configuration is needed only when you want to use Firebird-related services. To create this file, 
      the `firebird-driver`_ must be installed.

   .. note::

      The logging configuration is optional. When defined, it's automatically used by all Saturnin containers.
      To use per-container logging configuration, it's necessary to use the `--conifg` container option with 
      separate logging configuration file.

3. Command `show config` to show content of particular configuration file.

   Usage:: 
   
      > show config [OPTIONS] {main|user|firebird|logging|theme} 

      Show content of configuration file.
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    config_file      {main|user|firebird|logging|theme}     Configuration file                     │
      │                                                              [default: None]                        │
      │                                                              [required]                             │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

4. Command `edit config` to edit configuration file content with prefered editor (uses EDITOR environment variable
   or `editor` parameter of `main` or `user` configuration file).

   Usage:: 
   
      > edit config [OPTIONS] {main|user|firebird|logging|theme} 

      Edit configuration file.
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    config_file      {main|user|firebird|logging|theme}     Configuration file                     │
      │                                                              [default: None]                        │
      │                                                              [required]                             │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

Data files
**********

Saturnin uses number of data files:

1. Registry of installed services. 
2. Registry of installed applications.
3. Registry of OIDs.
4. Saturnin console command history.
5. Default log file.

The `saturnin console`_ command `list datafiles` prints paths to all data files used by Saturnin. An existence 
check is performed, and status of each file is indicated with `✔` (exists) and `✖` (missing) marks.

   ::

      > list datafiles
      ╭─ Saturnin data files ───────────────────────────────────────────────────────────────────────────────╮
      │ Installed services     ✔ /home/home/data/services.toml                                              │
      │ Installed applications ✔ /home/home/data/apps.toml                                                  │
      │ Registered OIDs        ✔ /home/home/data/oids.toml                                                  │
      │ Console history        ✔ /home/home/data/saturnin.hist                                              │
      │ Default log file       ✔ /home/home/logs/saturnin.log                                               │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯


.. note::  
   
   All these files may not exist when Saturnin is installed and initialized.

   * Service and application registries are updated automatically when packages are (un)installed by the Saturnin 
     console. If these registries are not synchronized with installed services and applications (for example, when 
     developing your services), they must be updated separately with the `update registry` command.

   * The `OID registry`_ is optional enhancement, and not necessary for Saturnin operation.

   * The console command history is managed automatically.

   * The default log file is optional, as it's used by default logging (also optional) configuration.

Managing Saturnin packages
==========================

Saturnin Butler services, Applications and other extensions must be installed into Saturnin virtual environment 
before they could be used. Saturnin uses standard `pip`_ utility to manage Python packages, and the console provides
several commands that use the pip version installed in Saturnin virtual environment. 

.. warning::

   While you can call the pip from this virtual environment directly, it's strongly recommended to use Saturnin 
   console commands, as they ensure that Saturnin registries are in sync with installed packages.

1. Command `install package`.

   Installs Python package into Saturnin virtual environment via `pip`.

   .. note:: This command is used also to upgrade installed packages using `-U` or `--upgrade` option.
    
   Usage::

      install package [options] <requirement specifier> [package-index-options] ...
      install package [options] -r <requirements file> [package-index-options] ...
      install package [options] [-e] <vcs project url> ...
      install package [options] [-e] <local project path> ...
      install package [options] <archive url/path> ...

   To list all available options, use `?install package` or `install package --help`.

2. Command `uninstall package`.

   Uninstalls Python package from Saturnin virtual environment via `pip`.
    
   Usage::

      uninstall package [options] <package> ...
      uninstall package [options] -r <requirements file> ...

   To list all available options, use `?uninstall package` or `uninstall package --help`.

   .. note::

      This command invokes `pip uninstall` command with implicit `--yes` parameter, so you're 
      not asked for confirmation.

3. Command `pip`.

   Runs `pip` package manager in Saturnin virtual environment.
    
   Usage::

      pip <command> [options]

   To list all available commands and options, use `?pip` or `pip --help`.

4. Command `list packages` lists installed distribution packages with Saturnin components.                                       

   .. note::

      This command does not list ALL packages installed in Saturnin virtual environment, but only those     
      that contain registered Saturnin components. To list all installed Python packages, 
      use: `pip list` command.

   Example::

      > list packages
              Installed Saturnin packages         
      ╭────────────────────────────────┬─────────╮
      │ Package                        │ Version │
      ├────────────────────────────────┼─────────┤
      │ saturnin-example-dummy         │ 0.1.0   │
      │ saturnin-core                  │ 0.8.0   │
      │ saturnin-example-app-dummy     │ 0.1.0   │
      │ saturnin-example-textio        │ 0.1.0   │
      │ saturnin-example-app-printfile │ 0.1.0   │
      │ saturnin-example-roman         │ 0.2.0   │
      ╰────────────────────────────────┴─────────╯

5. Command `list services`.
                                                                                                    
   Lists installed Saturnin services.                                                                    

   Usage::
      
      list services [OPTIONS]                                                                        
                                                                                                       
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --with-name        TEXT  List only services with this string in name                                │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   Example::

      > list services
                                           Registered services                                      
      ╭─────────────────────────────────┬─────────┬────────────────────────────────────────────────╮
      │ Service                         │ Version │ Description                                    │
      ├─────────────────────────────────┼─────────┼────────────────────────────────────────────────┤
      │ saturnin.binary.reader          │ 0.1.1   │ Binary data reader microservice                │
      │ saturnin.binary.writer          │ 0.1.1   │ Binary data writer microservice                │
      │ saturnin.example.roman          │ 0.2.0   │ Sample ROMAN service                           │
      │ saturnin.example.textio         │ 0.1.0   │ Sample TEXTIO microservice                     │
      │ saturnin.firebird.log.fromsrv   │ 0.2.1   │ Firebird log from server provider microservice │
      │ saturnin.firebird.log.parser    │ 0.2.1   │ Firebird log parser microservice               │
      │ saturnin.firebird.trace.parser  │ 0.1.1   │ Firebird trace parser microservice             │
      │ saturnin.firebird.trace.session │ 0.1.1   │ Firebird trace session provider microservice   │
      │ saturnin.micro.dummy            │ 0.1.0   │ Test dummy microservice                        │
      │ saturnin.proto.aggregator       │ 0.2.1   │ Protobuf data aggregator microservice          │
      │ saturnin.proto.filter           │ 0.2.1   │ Protobuf data filter microservice              │
      │ saturnin.proto.printer          │ 0.2.1   │ Protobuf data printer microservice             │
      │ saturnin.text.linefilter        │ 0.2.1   │ Text line filter microservice                  │
      │ saturnin.text.reader            │ 0.2.1   │ Text reader microservice                       │
      │ saturnin.text.writer            │ 0.2.1   │ Text writer microservice                       │
      ╰─────────────────────────────────┴─────────┴────────────────────────────────────────────────╯

6. Command `list applications`.

   Lists installed Saturnin applications.                                                                

   Usage::
      
      list applications [OPTIONS]                                                                    
                                                                                                                                                                                                        
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --with-name        TEXT  List only applications with this string in name                            │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   Example::

      > list applications
                                  Registered applications                            
      ╭─────────────────────────┬─────────┬───────────┬─────────────────────────────╮
      │ Application             │ Version │   Used    │ Description                 │
      ├─────────────────────────┼─────────┼───────────┼─────────────────────────────┤
      │ saturnin.app.dummy      │ 0.1.0   │     ✖     │ Test dummy application      │
      │ saturnin.app.print_file │ 0.1.0   │     ✔     │ Print text file application │
      ╰─────────────────────────┴─────────┴───────────┴─────────────────────────────╯

   .. note::

      Applications that are used in registered recipes are marked as `Used`.

7. Command `show service`.

   Show information about installed service.                                                             
                                                                                                       
   Usage::
      
      show service [SERVICE_ID]                                                            
                                                                                                                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │   service_id      [SERVICE_ID]  Service UID or name                                                 │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   Example::

      > show service saturnin.binary.reader
      UID:            3db461de-f32e-5514-910d-7d021a2436a5
      Name:           saturnin.binary.reader              
      Version:        0.1.1                               
      Vendor:         The Firebird Project                
      Classification: binary/reader                       
      Description:    Binary data reader microservice     
      Facilities:                                         
      API:                                                
      Distribution:   saturnin-core           

   .. note::

      The `Vendor` attribute normally displays the UUID of the vendor. If UUID is found in the OID registry, 
      the OID name is displayed instead.

8. Command `show application`.

   Show information about installed application.                                                         
                                                                                                       
   Usage::
      
      show application [APP_ID]                                                            
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │   app_id      [APP_ID]  Application UID or name                                                     │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

      Example::

         > show application saturnin.app.print_file
         UID:            c4aa5f0b-74b7-55ea-8fc8-e3eb41335049
         Name:           saturnin.app.print_file             
         Version:        0.1.0                               
         Vendor:         The Firebird Project                
         Classification: text/print                          
         Description:    Print text file application         
         Distribution:   saturnin-example-app-printfile   

   .. note::

      The `Vendor` attribute normally displays the UUID of the vendor. If UUID is found in the OID registry, 
      the OID name is displayed instead.

9. Command `update registry`.

   Updates registry of installed Saturnin components.                                                    

   The registry is updated automatically when Saturnin packages are manipulated with built-in `install`,   
   `uninstall` or `pip` commands. Manual update is required only when packages are added/updated/removed in  
   differet way.   

   Usage::
      
      update registry
                                                                                                       

.. important::

   Commands `list packages`, `list services`, `list applications`, `show service` and `show application` work
   with Saturnin registries. They will not provide accurate information if these registries are not synchronized
   with installed packages (see `update registry` command).

OID registry
============

The Firebird Butler spec recommends using UUID for identification purposes, and Saturnin follows that 
recommendation. Since standard UUIDs are not very suitable for ordinary users, UUIDs derived from the much 
more understandable OID are used.

Specifically, Saturnin uses version 5 UUIDs - UUIDs based on a SHA-1 hash of a namespace identifier 
(which is a UUID) and a name (which is a string).

The Firebird project has its own OID registered with IANA - `1.3.6.1.4.1.53446` (which in full-name form is
`iso.org.dod.internet.private.enterprise.firebird`) and maintains its own OID tree on GitHub, see 
the `firebird-uuid`_ repository. Firebird Butler, Saturnin, solution providers, protocols, etc. all have 
their own OID nodes and thus specific UUIDs (and names).

To facilitate work with UUIDs, Saturnin's own OID registry is provided, which is used to translate between 
UUIDs and OIDs, display additional information, etc. Before using this registry, it is necessary to fill 
the appropriate records with the `update oids` command.

1. Command `update oids`.

   Usage::
   
      update oids URL                                                                      
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │   url      URL   URL to OID node specification                                                      │
      │                  [default:                                                                          │
      │                  https://raw.githubusercontent.com/FirebirdSQL/firebird-uuid/master/root.oid]       │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   .. tip::

      OID names are available along with UUIDs in command completion once OID registry is updated.

2. Command `list oids`
                                                                                                       
   Lists registered OIDs.                                                                                 
                                                                                                       
   Usage::
      
      list oids [OPTIONS]                                                                            
                                                                                                       
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --with-name        TEXT  List only OIDs with this string in name                                    │
      │ --show-oids              Should OIDs instead UUIDs                                                  │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   Example::

      > list oids --with-name protocol
                            Registered OIDs with name containing 'protocol'                      
      ╭──────────────────────────────────────────────────┬──────────────────────────────────────╮
      │ OID Name                                         │ UUID                                 │
      ├──────────────────────────────────────────────────┼──────────────────────────────────────┤
      │ firebird.butler.protocol                         │ 15ab5c16-00e4-5fec-8928-c5d785d66729 │
      │ firebird.butler.platform.saturnin.protocol       │ 2068f86d-9154-58aa-acb2-b09cca9f9d18 │
      │ firebird.butler.platform.saturnin.protocol.dummy │ 4c546e1d-f208-50fb-8b67-100520cb599f │
      │ firebird.butler.platform.saturnin.protocol.iccp  │ 9b7ac9a3-d684-5955-b0ae-2f69e8666868 │
      │ firebird.butler.protocol.dummy                   │ a86ff2d2-73eb-593f-8b14-f2f7af0233d1 │
      │ firebird.butler.protocol.fbsp                    │ 98bd50a9-5863-551d-b19a-a76e2b2ee4d4 │
      │ firebird.butler.protocol.fbdp                    │ 34209338-6370-5e24-a28a-802814e6327c │
      ╰──────────────────────────────────────────────────┴──────────────────────────────────────╯

3. Command `show oid`
                                                                                                       
   Show information about OID.                                                                           
                                                                                                       
   Usage::
      
      show oid [OID]                                                                       
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │   oid      [OID]  OID name or GUID                                                                  │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   Example::

      > show oid firebird.butler.platform.saturnin
      OID:          1.3.6.1.4.1.53446.1.1.0                                                                  
      UID:          46cd9e8a-c697-5cb5-abb5-bceac5a17075                                                     
      Node name:    saturnin                                                                                 
      Full name:    firebird.butler.platform.saturnin                                                        
      Description:  Firebird Butler Development & Deployment Platform in Python 3, also provides reference   
                    implementations for Firebird Burtler standards                                           
      Contact:      Pavel Císař                                                                              
      E-mail:       pcisar@users.sourceforge.net                                                             
      Site:         https://firebirdsql.org/en/saturnin/                                                     
      Node spec.:   https://raw.githubusercontent.com/FirebirdSQL/saturnin/master/oid/saturnin.oid           
      Node type:    NODE                                                                                     
      Parent spec.: https://raw.githubusercontent.com/FirebirdSQL/Butler/master/oid/platforms.oid  

Working with recipes
====================

Recipes describing component configuration (including structural composition) can be used in two ways:

1. As a required parameter for the `saturnin-service` and `saturnin-bundle` tools. This method is particularly 
   suitable for the development and testing of saturnin-based solutions.
2. As executable commands in `saturnin console`_. This method is preferred for routine deployment of already 
   created solutions.

Saturnin console works with its own recipe repository. Recipes can be created directly in the console, 
or recipes created in another way can be installed (e.g. from the solution supplier or from the Saturnin 
application). All registered recipes can then be activated directly with the `run` command.

.. important::

   Due to the above, there is a restriction on the uniqueness of the recipe name. However, the same recipe can 
   be installed repeatedly, under different names (e.g. if several different variants of the recipe are needed).

.. tip::

   In addition to multiple installations of similar recipes under different names, different variants can be 
   created directly in the recipe. This is because a recipe can contain multiple sections describing the running 
   components. When activating the recipe, you can specify (using the `--section` option) an alternative name 
   for the section describing the components used.

   The names and structure of the sections differ according to the container used. 
   
   By default:
   
   * the `saturnin-bundle` container uses a "bundle" section with a `.ServiceBundleConfig` structure 
     that refers to the configuration sections of individual components. 
   
   * the `saturnin-service` container uses a "service" section with a `.ServiceExecConfig` structure. 
     The same section is then used to configure the running component.



The `saturnin console`_ provides next commands for work with recipes:

1. Command `create recipe`.
                                                                                                       
   Creates a recipe template that uses the specified Butler services. Such a template contains only      
   default settings and usually needs to be modified to achieve the desired results.                     

   .. note::

      The newly created recipe is automatically opened in the default editor for necessary modifications. 
      After saving, the recipe is automatically registered under the `run` command, so it can be run immediately.

   Usage::
      
      create recipe [OPTIONS] NAME COMPONENTS...                                                     
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    recipe_name      NAME           Recipe name                                                    │
      │                                      [default: None]                                                │
      │                                      [required]                                                     │
      │ *    components       COMPONENTS...  Recipe components                                              │
      │                                      [default: None]                                                │
      │                                      [required]                                                     │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --plain          Create recipe without comments                                                     │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯


2. Command `list recipes`.

   Lists installed (registered) Saturnin recipes.     

   Usage::
      
      list recipes

   Example::

      > list recipes
                                                 Installed recipes                                           
      ╭────────────┬─────────┬────────────────┬─────┬───────────────────────────────────────────────────────╮
      │ Name       │ Type    │ Execution mode │ App │ Description                                           │
      ├────────────┼─────────┼────────────────┼─────┼───────────────────────────────────────────────────────┤
      │ master     │ BUNDLE  │ NORMAL         │  ✖  │ This is all-in-one bundle recipe with various         │
      │            │         │                │     │ alternatives.                                         │
      │ log-print  │ BUNDLE  │ NORMAL         │  ✖  │ Sample processing pipeline for log from local         │
      │            │         │                │     │ Firebird server.                                      │
      │ dummy      │ SERVICE │ DAEMON         │  ✖  │ Dummy service for test purposes.                      │
      │ print-file │ BUNDLE  │ NORMAL         │  ✔  │ Print text file.                                      │
      │ test       │ BUNDLE  │ NORMAL         │  ✖  │ Not provided                                          │
      ╰────────────┴─────────┴────────────────┴─────┴───────────────────────────────────────────────────────╯      
                                                                                                       
3. Command `show recipe`.
                                                                                                      
   It analyzes the content of the recipe and displays its structure and configuration according to the default 
   sections of the container configuration. If the recipe contains several variants, it is necessary to enter 
   the name of the specific section for the configuration of the container to display them.

   Alternatively, it is possible to display the entire recipe in text form (with syntax highlighting).
                                                                                                 
   Usage::
      
      show recipe [OPTIONS] RECIPE_NAME                                                              
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    recipe_name      TEXT  Recipe name                                                             │
      │                             [default: None]                                                         │
      │                             [required]                                                              │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --section        TEXT  Configuration section name                                                   │
      │                        [default: None]                                                              │
      │ --raw                  Print recipe file content instead normal output                              │
      │ --help                 Show this message and exit.                                                  │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   Example::

      > show recipe log-print
      Name:        log-print                                                                                
      Type:        BUNDLE                                                                                   
      Exec. mode:  NORMAL                                                                                   
      Executor:    DEFAULT                                                                                  
      Application:                                                                                          
      Description: Sample processing pipeline for log from local Firebird server.                           

        Recipe components (default section)                                                                  
      ╭─────────────┬───────────────────────────────┬─────────┬─────────────────────────────────────────────╮
      │ Cfg. name   │ Component                     │ Version │ Description                                 │
      ├─────────────┼───────────────────────────────┼─────────┼─────────────────────────────────────────────┤
      │ from-server │ saturnin.firebird.log.fromsrv │ 0.2.1   │ Firebird log from server provider           │
      │             │                               │         │ microservice                                │
      │ log-parser  │ saturnin.firebird.log.parser  │ 0.2.1   │ Firebird log parser microservice            │
      │ log-print   │ saturnin.proto.printer        │ 0.2.1   │ Protobuf data printer microservice          │
      │ writer      │ saturnin.text.writer          │ 0.2.1   │ Text writer microservice                    │
      ╰─────────────┴───────────────────────────────┴─────────┴─────────────────────────────────────────────╯

        from-server configuration                                   
      ╭─────────────────────────┬──────────────────────────────────╮
      │ Parameter               │ Value                            │
      ├─────────────────────────┼──────────────────────────────────┤
      │ agent                   │ 212657dc26185f4ba8f5d8d42e99fe7e │
      │ logging_id              │ None                             │
      │ stop_on_close           │ True                             │
      │ pipe                    │ pipe-1                           │
      │ pipe_address            │ inproc://pipe-1                  │
      │ pipe_mode               │ BIND                             │
      │ pipe_format             │ text/plain;charset=utf-8         │
      │ batch_size              │ 50                               │
      │ ready_schedule_interval │ 1000                             │
      │ server                  │ local                            │
      │ max_chars               │ 65535                            │
      ╰─────────────────────────┴──────────────────────────────────╯

        log-parser configuration                                                                            
      ╭────────────────────────────────┬───────────────────────────────────────────────────────────────────╮
      │ Parameter                      │ Value                                                             │
      ├────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
      │ agent                          │ a93975c3d8c45e19b89809391cafa8d8                                  │
      │ logging_id                     │ None                                                              │
      │ propagate_input_error          │ True                                                              │
      │ input_pipe                     │ pipe-1                                                            │
      │ input_pipe_address             │ inproc://pipe-1                                                   │
      │ input_pipe_mode                │ CONNECT                                                           │
      │ input_pipe_format              │ text/plain;charset=utf-8                                          │
      │ input_batch_size               │ 5                                                                 │
      │ input_ready_schedule_interval  │ 1000                                                              │
      │ output_pipe                    │ pipe-2                                                            │
      │ output_pipe_address            │ inproc://pipe-2                                                   │
      │ output_pipe_mode               │ BIND                                                              │
      │ output_pipe_format             │ application/x.fb.proto;type=saturnin.core.protobuf.fblog.LogEntry │
      │ output_batch_size              │ 50                                                                │
      │ output_ready_schedule_interval │ 1000                                                              │
      ╰────────────────────────────────┴───────────────────────────────────────────────────────────────────╯

        log-print configuration                                                                              
      ╭────────────────────────────────┬────────────────────────────────────────────────────────────────────╮
      │ Parameter                      │ Value                                                              │
      ├────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
      │ agent                          │ a58a9b30117a529e8084b9f8daf96d3e                                   │
      │ logging_id                     │ None                                                               │
      │ propagate_input_error          │ True                                                               │
      │ input_pipe                     │ pipe-2                                                             │
      │ input_pipe_address             │ inproc://pipe-2                                                    │
      │ input_pipe_mode                │ CONNECT                                                            │
      │ input_pipe_format              │ application/x.fb.proto;type=saturnin.core.protobuf.fblog.LogEntry  │
      │ input_batch_size               │ 5                                                                  │
      │ input_ready_schedule_interval  │ 1000                                                               │
      │ output_pipe                    │ pipe-3                                                             │
      │ output_pipe_address            │ inproc://pipe-3                                                    │
      │ output_pipe_mode               │ BIND                                                               │
      │ output_pipe_format             │ text/plain;charset=utf-8                                           │
      │ output_batch_size              │ 5                                                                  │
      │ output_ready_schedule_interval │ 1000                                                               │
      │ template                       │ {data.timestamp.ToDatetime()!s}                                    │
      │                                │ {utils.short_enum_name('saturnin.core.protobuf.SeverityLevel',dat… │
      │                                │ {utils.short_enum_name('saturnin.core.protobuf.fblog.FirebirdFaci… │
      │                                │ data.facility):10} {data.code} {data.message}{utils.LF}            │
      │ func                           │ None                                                               │
      ╰────────────────────────────────┴────────────────────────────────────────────────────────────────────╯

        writer configuration                                        
      ╭─────────────────────────┬──────────────────────────────────╮
      │ Parameter               │ Value                            │
      ├─────────────────────────┼──────────────────────────────────┤
      │ agent                   │ 4e606fdf3fa95d18a7149448a8085aab │
      │ logging_id              │ None                             │
      │ stop_on_close           │ True                             │
      │ pipe                    │ pipe-3                           │
      │ pipe_address            │ inproc://pipe-3                  │
      │ pipe_mode               │ CONNECT                          │
      │ pipe_format             │ text/plain;charset=utf-8         │
      │ batch_size              │ 5                                │
      │ ready_schedule_interval │ 1000                             │
      │ filename                │ stdout                           │
      │ file_format             │ text/plain;charset=utf-8         │
      │ file_mode               │ WRITE                            │
      ╰─────────────────────────┴──────────────────────────────────╯

   Example:

   .. code-block:: cfg

      > show recipe --raw log-print
      [saturnin.recipe]                                                                                      
      recipe_type = bundle                                                                                   
      execution_mode = normal                                                                                
      description = Sample processing pipeline for log from local Firebird server.                           
                                                                                                       
      [bundle]                                                                                               
      agents = from-server, log-parser, log-print, writer                                                    
                                                                                                       
      [from-server]                                                                                          
      agent = 212657dc-2618-5f4b-a8f5-d8d42e99fe7e                                                           
      pipe = pipe-1                                                                                          
      pipe_address = inproc://${pipe}                                                                        
      pipe_mode = bind                                                                                       
      pipe_format = text/plain;charset=utf-8                                                                 
      server = local                                                                                         
                                                                                                                                                                                                              
      [log-parser]                                                                                           
      agent = a93975c3-d8c4-5e19-b898-09391cafa8d8                                                           
      ; Filter config                                                                                        
      input_pipe = pipe-1                                                                                    
      input_pipe_address = inproc://${input_pipe}                                                            
      input_pipe_mode = connect                                                                              
      input_pipe_format = text/plain;charset=utf-8                                                           
      input_batch_size = 5                                                                                   
      ;                                                                                                      
      output_pipe = pipe-2                                                                                   
      output_pipe_address = inproc://${output_pipe}                                                          
      output_pipe_mode = bind                                                                                
      output_batch_size = 50                                                                                 
                                                                                                       
      [log-print]                                                                                            
      agent = a58a9b30-117a-529e-8084-b9f8daf96d3e                                                           
      ; Filter config                                                                                        
      input_pipe = pipe-2                                                                                    
      input_pipe_address = inproc://${input_pipe}                                                            
      input_pipe_mode = connect                                                                              
      input_pipe_format = application/x.fb.proto;type=saturnin.core.protobuf.fblog.LogEntry                  
      input_batch_size = 5                                                                                   
      ;                                                                                                      
      output_pipe = pipe-3                                                                                   
      output_pipe_address = inproc://${output_pipe}                                                          
      output_pipe_mode = bind                                                                                
      output_batch_size = 5                                                                                  
      ;                                                                                                      
      template = {data.timestamp.ToDatetime()!s}                                                             
      {utils.short_enum_name('saturnin.core.protobuf.SeverityLevel',data.level):8}                           
      {utils.short_enum_name('saturnin.core.protobuf.fblog.FirebirdFacility', data.facility):10} {data.code} 
      {data.message}{utils.LF}                                                                               

      [writer]                                                                                               
      agent = 4e606fdf-3fa9-5d18-a714-9448a8085aab                                                           
      pipe = pipe-3                                                                                          
      pipe_address = inproc://${pipe}                                                                        
      pipe_mode = connect                                                                                    
      pipe_format = text/plain;charset=utf-8                                                                 
      ;filename = /home/job/python/data/parsed.log                                                           
      filename = stdout                                                                                      
      file_format = text/plain;charset=utf-8                                                                 
      file_mode = write                                                                                      
           
4. Command `edit recipe`.
                                                                                                       
   Edit recipe.                                                                                          
                                                                                                       
   Usage::
      
      edit recipe RECIPE_NAME                                                              
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    recipe_name      TEXT  Recipe name                                                             │
      │                             [default: None]                                                         │
      │                             [required]                                                              │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

5. Command `install recipe`.
                                                                                                       
   Installs a new recipe from an external recipe file or from an installed application. Once installed,  
   recipe can be executed immediately with the `run` command.

   .. note::

      It performs only basic recipe validation, i.e. that required sections (recipe + container) are present,
      and that components required by recipe are installed.
                                                                                                       
   Usage::
      
      install recipe [OPTIONS]                                                                       
                                                                                                       
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --recipe-name        TEXT  Recipe name (default is recipe file name / application name)             │
      │                            [default: None]                                                          │
      │ --recipe-file        FILE  Recipe file. Mutually exclusive with --app-id                            │
      │                            [default: None]                                                          │
      │ --app-id             TEXT  Application UID or name                                                  │
      │                            [default: None]                                                          │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯


6. Command `uninstall recipe`.

   Uninstall recipe. Can optionally save the recipe to file before it's deleted.
                                                                                                       
   Usage::
      
      uninstall recipe [OPTIONS] [RECIPE_NAME]                                                       
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │   recipe_name      [RECIPE_NAME]  The name of the recipe to be uninstalled                          │
      │                                   [default: None]                                                   │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯
      ╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────╮
      │ --save-to        FILE  File where recipe should be saved before it's removed                        │
      │                        [default: None]                                                              │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

7. Command `run`.

   The "run" command is used to activate the containers according to the installed recipes. Internally, each 
   installed recipe is made available as a separate sub-command under the "run" command. The parameters of the 
   individual commands depend on the container or application used in the recipe.

   The specific behavior of the command depends on the components used, the application (if used) and the execution 
   mode:
   
   * Recipe commands with `DAEMON` execution mode start the container as a separate daemon process, and the console 
     immediately returns to the command prompt. 
   
   * Recipe commands with `NORMAL` execution mode will start the container, and the console will return to the command 
     prompt only after the container has finished running.

Daemon processes
================

Containers can be run as daemon processes using the `saturnin-daemon` tool, or using the saturnin console and 
installed recipes with `DAEMON` execution mode. The management of these daemon processes differs depending on 
the activation method:

* Processes started with `saturnin-daemon` must be managed with your own resources (see documentation for the 
  saturnin-daemon tool and working with PID files).

* Processes started using the `saturnin console`_ can be managed in the console using commands for working with 
  daemon processes.

1. Command `list daemons`.
                                                                                                       
   List running Saturnin daemons.     
                                                                                                       
   Usage::
      
      list daemons

   Example::

      > list daemons
                              Running daemons                         
      ╭───────┬──────────┬────────┬──────────────────────────────────╮
      │ PID   │ Status   │ Recipe │ Description                      │
      ├───────┼──────────┼────────┼──────────────────────────────────┤
      │ 14082 │ sleeping │ dummy2 │ Dummy service for test purposes. │
      │ 14087 │ sleeping │ dummy2 │ Dummy service for test purposes. │
      ╰───────┴──────────┴────────┴──────────────────────────────────╯

2. Command `show daemon`.
                                                                                                       
   Show information about running Saturnin daemon.                                                       

   Usage::
      
      show daemon PID                                                                      
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    pid      INTEGER  [default: None] [required]                                                   │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

   Example::

      > show daemon 14082
        Process 14082                                                                                        
      ╭─────────────────┬───────────────────────────────────────────────────────────────────────────────────╮
      │ Status:         │ sleeping                                                                          │
      │ Created:        │ 2023-03-27 15:14:49                                                               │
      │ Run time:       │ 0:02:58.567710                                                                    │
      ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┤
      │ # threads:      │ 4                                                                                 │
      │ # files:        │ 12                                                                                │
      │ # INET con.:    │ 0                                                                                 │
      ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┤
      │ Name:           │ saturnin-bundle                                                                   │
      │ Executable:     │ /usr/bin/python3.9                                                                │
      │ Cmd. line:      │ /home/job/python/envs/saturnin/bin/python,                                        │
      │                 │ /home/job/python/envs/saturnin/bin/saturnin-bundle, -q,                           │
      │                 │ /home/job/python/projects/saturnin/home/data/recipes/dummy2.cfg                   │
      │ CWD:            │ /home/job/python/projects/saturnin                                                │
      │ User:           │ pcisar                                                                            │
      ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┤
      │ CPU user:       │ 0.28                                                                              │
      │ CPU system:     │ 0.04                                                                              │
      │ CPU I/O wait:   │ 0.0                                                                               │
      ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┤
      │ RSS (bytes):    │ 26.84 MiB                                                                         │
      │ VMS (bytes):    │ 205.64 MiB                                                                        │
      ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┤
      │ Read count:     │ 1013                                                                              │
      │ Write count:    │ 4                                                                                 │
      │ Bytes read:     │ 1445888                                                                           │
      │ Bytes written:  │ 0                                                                                 │
      ╰─────────────────┴───────────────────────────────────────────────────────────────────────────────────╯


3. Command `stop daemon`.

   Stop running Saturnin daemon.                                                                         
                                                                                                       
   Usage::
      
      stop daemon PID                                                                      
                                                                                                       
      ╭─ Arguments ─────────────────────────────────────────────────────────────────────────────────────────╮
      │ *    pid      INTEGER  [default: None] [required]                                                   │
      ╰─────────────────────────────────────────────────────────────────────────────────────────────────────╯

.. _setuptools: https://pypi.org/project/setuptools/
.. _ctypes: http://docs.python.org/library/ctypes.html
.. _PYPI: https://pypi.org/
.. _pip: https://pypi.org/project/pip/
.. _pipx: https://pypa.github.io/pipx/
.. _firebird-base: https://firebird-base.rtfd.io
.. _firebird-driver: https://pypi.org/project/firebird-driver/
.. _introduction to Firebird Butler: https://firebird-butler.readthedocs.io/en/latest/introduction.html
.. _saturnin-core: https://github.com/FirebirdSQL/saturnin-core
.. _Saturnin CORE: https://saturnin-core.rtfd.io/
.. _Saturnin SDK: https://saturnin-sdk.rtfd.io/
.. _saturnin-sdk: https://github.com/FirebirdSQL/saturnin-sdk
.. _FBSP: https://firebird-butler.readthedocs.io/en/latest/rfc/4/FBSP.html
.. _FBDP: https://firebird-butler.readthedocs.io/en/latest/rfc/9/FBDP.html
.. _Firebird Butler services: https://firebird-butler.readthedocs.io/en/latest/rfc/3/FBSD.html
.. _firebird-uuid: https://github.com/FirebirdSQL/firebird-uuid
