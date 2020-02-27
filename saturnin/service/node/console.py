#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Runtime node service
# FILE:           saturni.sarvice.node.console.py
# DESCRIPTION:    Saturnin node console (CLI version)
# CREATED:        14.6.2019
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2019 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

"""Saturnin - Runtime node console (CLI version)


"""

import typing as t
import logging
from logging.config import fileConfig
import sys
import os
from uuid import UUID, uuid1
from socket import getfqdn
import cmd
import zmq
from argparse import ArgumentParser, Action, Namespace, FileType
from configparser import ConfigParser, ExtendedInterpolation, DEFAULTSECT
from pkg_resources import iter_entry_points
from tabulate import tabulate
from saturnin.core import VENDOR_UID
from saturnin.core.types import State, ZMQAddress, AddressDomain, PeerDescriptor, \
     AgentDescriptor, ServiceDescriptor, SaturninError, StopError
from saturnin.core.collections import Registry
from saturnin.core.config import Config, ServiceConfig, UUIDOption, BoolOption
from saturnin.core.base import ChannelManager, DealerChannel
from . import node_pb2 as pb
from .client import SaturninNodeClient

__VERSION__ = '0.1'

CONSOLE_AGENT_UID = UUID('0a82fd0e-9339-11e9-8c3d-5404a6a1fd6e')

SECTION_LOCAL_ADDRESS = 'local_address'
SECTION_NODE_ADDRESS = 'node_address'
SECTION_NET_ADDRESS = 'net_address'
SECTION_SERVICE_UID = 'service_uid'
SECTION_PEER_UID = 'peer_uid'

def title(text: str, size: int = 80, char: str = '='):
    "Returns centered title surrounded by char."
    return f"  {text}  ".center(size, char)

# Classes

class ConsoleConfig(Config):
    """Console configuration"""
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.service_uid = UUIDOption('service_uid',
                                      "Service UID (agent.uid in the Service Descriptor)",
                                      required=True)
        self.singleton = BoolOption('singleton',
                                    "When True, start only one service instance",
                                    default=False)

class UpperAction(Action):
    "Converts argument to uppercase."
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

class NodeConsole(cmd.Cmd):
    """Saturnin - Runtime node console

Attributes:
    :options: Command-line options (arguments)
    :ctx:     ZMQ Context
    :mngr:    ChannelManager
    :chn:     DealerChannel used for communication with node service.
    :peer:    Console PeerDescriptor
    :agent:   Console AgentDescriptor
    :node:    SaturninNodeClient
    :file:    Output file
"""
    def __init__(self, options: Namespace, completekey='tab', stdin=None, stdout=None):
        ""
        super().__init__(completekey, stdin, stdout)
        peer_uid: UUID = uuid1()
        self.options: Namespace = options
        self.ctx: zmq.Context = zmq.Context.instance()
        self.mngr: ChannelManager = ChannelManager(self.ctx)
        self.chn: DealerChannel = DealerChannel(b'node-console:' + peer_uid.hex.encode('ascii'), False)
        self.mngr.add(self.chn)
        self.peer: PeerDescriptor = PeerDescriptor(peer_uid, os.getpid(), getfqdn())
        self.agent: AgentDescriptor = AgentDescriptor(CONSOLE_AGENT_UID,
                                                      "Saturnin node console",
                                                      __VERSION__,
                                                      VENDOR_UID,
                                                      'system/console')
        self.node: SaturninNodeClient = SaturninNodeClient(self.chn, self.peer, self.agent)
        self.file: t.IO = None
        self.log: logging.Logger = logging.getLogger('nodeconsole')
        self.conf: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
        self.ext_cfg: ConsoleConfig = ConsoleConfig('console_cfg', "Node console configuration")

        self.service_registry: Registry = Registry()
        #
        self.__show_completion: t.List = ['installed', 'running', 'providers']
        self.__seen_agents: t.Set = set()
        self.__seen_peers: t.Set = set()
        self.__user_sections: t.List = []
        #
        if 'endpoint' in vars(options) and options.endpoint:
            self.cmdqueue.append('attach %s' % options.endpoint)
    def verbose(self, *args, **kwargs) -> None:
        "Log verbose output, not propagated to upper loggers."
        if self.options.verbose:
            self.log.debug(*args, **kwargs)
    def initialize(self) -> None:
        "Console initialization"
        self.conf[SECTION_LOCAL_ADDRESS] = {}
        self.conf[SECTION_NODE_ADDRESS] = {}
        self.conf[SECTION_NET_ADDRESS] = {}
        self.conf[SECTION_SERVICE_UID] = {}
        self.conf[SECTION_PEER_UID] = {}
        self.conf.read_file(self.options.config)
        # Defaults
        self.conf[DEFAULTSECT]['here'] = os.getcwd()
        if self.options.output_dir is None:
            self.conf[DEFAULTSECT]['output_dir'] = os.getcwd()
        else:
            self.conf[DEFAULTSECT]['output_dir'] = self.options.output_dir
        #
        for section in self.conf.sections():
            if self.conf.has_option(section, 'services'):
                self.__user_sections.append(section.lstrip('run_'))
            elif self.conf.has_option(section, 'service_uid'):
                self.__user_sections.append(section)
        # Logging configuration
        if self.conf.has_section('loggers'):
            self.options.config.seek(0)
            fileConfig(self.options.config)
        else:
            logging.basicConfig(format='%(asctime)s %(processName)s:'\
                                '%(threadName)s:%(name)s %(levelname)s: %(message)s')
        logging.getLogger().setLevel(self.options.log_level)
        # Script output configuration
        self.log.setLevel(logging.DEBUG)
        self.log.propagate = False
        if not self.options.log_only:
            output: logging.StreamHandler = logging.StreamHandler(sys.stdout)
            output.setFormatter(logging.Formatter())
            lvl = logging.INFO
            if self.options.verbose:
                lvl = logging.DEBUG
            elif self.options.quiet:
                lvl = logging.ERROR
            output.setLevel(lvl)
            self.log.addHandler(output)
        self.options.config.close()
        # Installed services
        self.service_registry.extend(entry.load() for entry in
                                     iter_entry_points('saturnin.service'))
        self.conf[SECTION_SERVICE_UID] = dict((sd.agent.name, sd.agent.uid.hex) for sd
                                              in self.service_registry)
        for svc in self.service_registry:
            self.note_agent(svc.agent)
    def finalize(self) -> None:
        "Finalize the console."
        self.close()
        self.node.close()
        self.mngr.shutdown()
        self.ctx.term()
    def close(self):
        "Close the output file if needed."
        if self.file:
            self.file.close()
            self.file = None
    def get_peer_uid(self, svc_name: str) -> UUID:
        """Returns peer uid of running service or None."""
        reply: pb.ReplyRunningServices = self.node.get_running()
        for service in reply.services:
            self.note_peer(service.peer)
            self.note_agent(service.agent)
            if service.agent.name == svc_name:
                return UUID(bytes=service.peer.uid)
        return None
    def note_peer(self, peer):
        "Remembers peer uid"
        self.__seen_peers.add(peer.uid if isinstance(peer.uid, UUID) else UUID(bytes=peer.uid))
    def note_agent(self, agent):
        "Remembers agent uids"
        self.__seen_agents.add(agent.uid if isinstance(agent.uid, UUID) else UUID(bytes=agent.uid))
    def precmd(self, line: str) -> str:
        "Hook method. Converts input to lowercase."
        line = line.lower()
        if self.file and not (line.startswith('run') or line.startswith('eof')):
            print(line, file=self.file)
        return line
    def emptyline(self):
        "We ignore empty lines."
        return
    def do_attach(self, line: str) -> bool:
        """Attach to Saturnin node.

Format:
    ATTACH <endpoint>
"""
        try:
            if self.node.is_connected():
                self.node.close()
                self.chn.drop_socket()
                self.chn.create_socket()
            self.node.open(line)
        except Exception as exc:
            self.log.error('ERROR:', exc)
        else:
            self.log.info("Attached to saturnin node at %s" % line)
    def do_show(self, line: str) -> bool:
        """Show various information about node and services.

Format:
    SHOW INSTALLED - Show information about services installed on node.
    SHOW RUNNING - Show information about services running on node.
    SHOW PROVIDERS <intreface_uid> - Show services that provide specified interface.
"""
        if not self.node.is_connected():
            print("Satunin node not attached.")
            return
        try:
            if line == 'installed':
                reply = self.node.get_installed()
                table = []
                for service in reply.services:
                    self.note_agent(service.agent)
                    table.append([service.agent.name, service.agent.version,
                                  UUID(bytes=service.agent.uid),
                                  service.agent.classification])
                self.log.info("Services installed on node:")
                self.log.info(tabulate(table, headers=('name', 'version', 'agent uid',
                                                       'classification'),
                               tablefmt="grid"))
            elif line == 'running':
                reply: pb.ReplyRunningServices = self.node.get_running()
                table = []
                for service in reply.services:
                    self.note_agent(service.agent)
                    self.note_peer(service.peer)
                    table.append([UUID(bytes=service.peer.uid), service.peer.host,
                                  service.peer.pid, pb.ExecutionModeEnum.Name(service.mode),
                                  service.agent.name, service.agent.version,
                                  '\n'.join(service.endpoints)])
                self.log.info("Services running on node:")
                self.log.info(tabulate(table, headers=('peer uid', 'host', 'pid', 'mode',
                                                       'name', 'version', 'endpoints'),
                               tablefmt="grid"))
            elif line == 'providers':
                pass
            else:
                self.log.error("Unknown SHOW command: %s" % line)
        except Exception as exc:
            self.log.error('ERROR:', exc)
    def complete_show(self, text: str, line: str, begidx: int, endidx: int) -> t.List:
        """Command completion for SHOW command."""
        return [f for f in self.__show_completion if f.startswith(text)]
    def do_start(self, line: str) -> bool:
        """Start service.

Format:
    START <config>[, <config>]

Arguments:
    config: Section name in current configuration file with service specification
"""
        if not self.node.is_connected():
            print("Satunin node not attached.")
            return
        try:
            # Create list of service sections
            sections = []
            for job_name in (x.strip() for x in line.split(', ')):
                job_section = 'run_%s' % job_name
                if self.conf.has_section(job_name):
                    sections.append(job_name)
                elif self.conf.has_section(job_section):
                    if not self.conf.has_option(job_section, 'services'):
                        raise StopError("Missing 'services' option in section '%s'" %
                                        job_section)
                    for name in (value.strip() for value in self.conf.get(job_section,
                                                                          'services').split(',')):
                        if not self.conf.has_section(name):
                            raise StopError("Configuration does not have section '%s'" % name)
                        sections.append(name)
                else:
                    raise StopError("Configuration does not have section '%s' or '%s'" %
                                    (job_name, job_section))
            # Validate configuration of services
            services = []
            for svc_section in sections:
                if not self.conf.has_option(svc_section, self.ext_cfg.service_uid.name):
                    raise StopError("Missing '%s' option in section '%s'" % (self.ext_cfg.service_uid.name,
                                                                             svc_section))
                self.ext_cfg.clear()
                self.ext_cfg.load_from(self.conf, svc_section)
                svc: ServiceDescriptor = self.service_registry.get(self.ext_cfg.service_uid.value)
                if svc is None:
                    raise StopError("Unknown service '%s'" % self.ext_cfg.service_uid.value)
                cfg: ServiceConfig = svc.config()
                try:
                    cfg.load_from(self.conf, svc_section)
                    cfg.validate()
                except (SaturninError, TypeError, ValueError) as exc:
                    raise StopError("Error in configuration section '%s'\n%s" % \
                                    (svc_section, str(exc)))
                services.append((svc_section, svc, cfg, self.ext_cfg.singleton.value))
            #
            for section_name, svc, cfg, singleton in services:
                # print configuration
                svc: ServiceDescriptor
                cfg: ServiceConfig
                self.verbose(title("Task '%s'" % section_name, char='-'))
                self.verbose("service_uid = %s [%s]" % (svc.agent.uid, svc.agent.name))
                self.verbose("singleton   = %s" % ('Yes' if singleton else 'No'))
                for option in cfg.options:
                    self.verbose("%s" % option.get_printout())
            self.verbose(title("Starting services"))
            #
            for section_name, svc, cfg, singleton in services:
                # refresh configuration to fetch actual addresses
                self.log.info("Starting service '%s', task '%s'", svc.agent.name,
                              section_name)
                cfg.load_from(self.conf, section_name)
                #
                reply: pb.ReplyStartService = \
                    self.node.start_service(svc.agent.uid, cfg, section_name,
                                            singleton=singleton)
                #
                if reply is None:
                    print('start_service returned NONE, no exception')
                    return
                if reply.service.endpoints:
                    # Update addresses
                    for endpoint in reply.service.endpoints:
                        endpoint = ZMQAddress(endpoint)
                        if endpoint.domain == AddressDomain.LOCAL:
                            self.conf[SECTION_LOCAL_ADDRESS][section_name] = endpoint
                        elif endpoint.domain == AddressDomain.NODE:
                            self.conf[SECTION_NODE_ADDRESS][section_name] = endpoint
                        else:
                            self.conf[SECTION_NET_ADDRESS][section_name] = endpoint
                #
                table = []
                table.append(['peer uid', UUID(bytes=reply.service.peer.uid)])
                table.append(['mode', pb.ExecutionModeEnum.Name(reply.service.mode)])
                table.append(['endpoints', '\n'.join(reply.service.endpoints)])
                self.log.info("Service started:")
                self.log.info(tabulate(table, tablefmt="grid"))
        except SaturninError as exc:
            self.log.error('ERROR: %s', exc)
        except Exception as exc:
            self.log.exception(exc)
    def complete_start(self, text: str, line: str, begidx: int, endidx: int) -> t.List:
        """Command completion for START command."""
        return [x for x in self.__user_sections if x.startswith(text)]
    def do_stop(self, line: str) -> bool:
        """Stop running service.

Format:
    STOP <service_uid> | ALL
"""
        if not self.node.is_connected():
            self.log.error("Satunin node not attached.")
            return
        uids = []
        if line.strip().upper() == 'ALL':
            reply: pb.ReplyRunningServices = self.node.get_running()
            for service in reply.services:
                uids.append(UUID(bytes=service.peer.uid))
        else:
            try:
                uid = UUID(line)
            except ValueError:
                uid = self.get_peer_uid(line)
                if not uid:
                    self.log.error("Service '%s' is not running." % line)
                    return
            uids.append(uid)
        for uid in uids:
            try:
                reply = self.node.stop_service(uid)
                state = 'STOPPED' if State(reply) == State.STOPPED else State(reply).name
                self.log.info("Service %s %s" % (uid, state))
            except Exception as exc:
                self.log.error('ERROR:', exc)
    def complete_stop(self, text: str, line: str, begidx: int, endidx: int) -> t.List:
        """Command completion for STOP command."""
        return [x for x in (str(x) for x in self.__seen_peers) if x.startswith(text)]
    def do_shutdown(self, line: str) -> bool:
        """Shuts down the Saturnin node, terminating all running services.
Format:
    SHUTDOWN
"""
        if not self.node.is_connected():
            print("Satunin node not attached.")
            return
        try:
            self.node.shutdown()
            self.node.close()
            self.chn.drop_socket()
            self.chn.create_socket()
            print("Saturnin node successfully shut down.")
        except Exception as exc:
            print('ERROR:', exc)
    def do_exit(self, line: str) -> bool:
        """Terminate the node console.

Format:
    EXIT
"""
        return True
    def do_record(self, arg):
        """Save future commands to file.

Format:
    RECORD <filename>
"""
        self.file = open(arg, 'w')
    def do_eof(self, arg):
        """Stop recording commands started by RECORD, and close the file.

Format:
    EOF
"""
        self.close()
    def do_run(self, arg):
        """Playback commands from a file.

Format:
    RUN <filename>
"""
        self.close()
        with open(arg) as f:
            self.cmdqueue.extend(f.read().splitlines())

def main():
    "Main function"

    into = """Saturnin node console v%s
Type 'help' or '?' for list of commands.
""" % __VERSION__

    logging.basicConfig(format='%(levelname)s:%(threadName)s:%(name)s:%(message)s')
    description = """Saturnin node console."""
    parser = ArgumentParser(description=description)
    parser.add_argument('--version', action='version', version='%(prog)s '+__VERSION__)

    group = parser.add_argument_group("run arguments")
    group.add_argument('-c', '--config', metavar='FILE',
                       type=FileType(mode='r', encoding='utf8'),
                       help="Configuration file")
    group.add_argument('-e', '--endpoint', help="ZMQ addresses of the Saturnin node")
    group.add_argument('-o', '--output-dir', metavar='DIR',
                       help="Force directory for log files and other output")

    group = parser.add_argument_group("output arguments")
    group.add_argument('-v', '--verbose', action='store_true', help="Verbose output")
    group.add_argument('-q', '--quiet', action='store_true', help="No screen output")
    group.add_argument('--log-only', action='store_true',
                       help="Suppress all screen output including error messages")
    group.add_argument('-l', '--log-level', action=UpperAction,
                       choices=[x.lower() for x in logging._nameToLevel
                                if isinstance(x, str)],
                       help="Logging level")
    group.add_argument('--trace', action='store_true',
                       help="Log unexpected errors with stack trace")
    parser.set_defaults(log_level='WARNING', config='nodeconsole.cfg',
                             output_dir='${here}')

    args = parser.parse_args()
    logger = logging.getLogger()
    logger.setLevel(args.log_level)

    console = NodeConsole(args)
    try:
        console.initialize()
        console.cmdloop(into)
    except KeyboardInterrupt:
        pass
    finally:
        console.finalize()

