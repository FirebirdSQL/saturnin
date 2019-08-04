#!/usr/bin/python
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

import logging
import cmd
from typing import List
import os
from uuid import UUID, uuid1
from socket import getfqdn
from argparse import ArgumentParser, Action, Namespace
import zmq
from tabulate import tabulate
from firebird.butler.fbsd_pb2 import StateEnum
from saturnin.sdk import VENDOR_UID, PLATFORM_UID, PLATFORM_VERSION
from saturnin.sdk.types import PeerDescriptor, AgentDescriptor, SaturninError, \
     ExecutionMode
from saturnin.sdk.base import ChannelManager, DealerChannel
from saturnin.service.node import node_pb2 as pb
from saturnin.service.node.client import SaturninNodeClient

__VERSION__ = '0.1'

CONSOLE_AGENT_UID = UUID('0a82fd0e-9339-11e9-8c3d-5404a6a1fd6e')

# Classes

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
        peer_uid = uuid1()
        self.options = options
        self.ctx: zmq.Context = zmq.Context.instance()
        self.mngr = ChannelManager(self.ctx)
        self.chn = DealerChannel(b'node-console:' + peer_uid.hex.encode('ascii'), False)
        self.mngr.add(self.chn)
        self.peer: PeerDescriptor = PeerDescriptor(peer_uid, os.getpid(), getfqdn())
        self.agent: AgentDescriptor = AgentDescriptor(CONSOLE_AGENT_UID,
                                                      "Saturnin node console",
                                                      __VERSION__,
                                                      VENDOR_UID,
                                                      'system/console',
                                                      PLATFORM_UID,
                                                      PLATFORM_VERSION
                                                     )
        self.node = SaturninNodeClient(self.chn, self.peer, self.agent)
        self.file = None
        self.__show_completion = ['installed', 'running', 'providers']
        self.__seen_agents = set()
        self.__seen_peers = set()
        #
        if 'endpoint' in vars(options):
            self.cmdqueue.append('attach %s' % options.endpoint)
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
    def get_service_uid(self, svc_name: str) -> UUID:
        """Returns uid of installed service or None."""
        reply = self.node.get_installed()
        for service in reply.services:
            self.note_agent(service.agent)
            if service.agent.name == svc_name:
                return UUID(bytes=service.agent.uid)
        return None
    def get_peer_uid(self, svc_name: str) -> UUID:
        """Returns peer uid of running service or None."""
        reply = self.node.get_running()
        for service in reply.services:
            self.note_peer(service.peer)
            self.note_agent(service.agent)
            if service.agent.name == svc_name:
                return UUID(bytes=service.peer.uid)
        return None
    def note_peer(self, peer):
        "Remembers peer uid"
        self.__seen_peers.add(UUID(bytes=peer.uid))
    def note_agent(self, agent):
        "Remembers agent uids"
        self.__seen_agents.add(UUID(bytes=agent.uid))
        #self.__seen_agents.add(UUID(bytes=agent.vendor.uid))
        #self.__seen_agents.add(UUID(bytes=agent.platform.uid))
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
            print('ERROR:', exc)
        else:
            print("Attached to saturnin node at %s" % line)
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
                print("Services installed on node:")
                print(tabulate(table, headers=('name', 'version', 'agent uid',
                                               'classification'),
                               tablefmt="grid"))
            elif line == 'running':
                reply = self.node.get_running()
                table = []
                for service in reply.services:
                    self.note_agent(service.agent)
                    self.note_peer(service.peer)
                    table.append([UUID(bytes=service.peer.uid), service.peer.host,
                                  service.peer.pid, pb.StartModeEnum.Name(service.mode),
                                  service.agent.name, service.agent.version,
                                  '\n'.join(service.endpoints)])
                print("Services running on node:")
                print(tabulate(table, headers=('peer uid', 'host', 'pid', 'mode',
                                               'name', 'version', 'endpoints'),
                               tablefmt="grid"))
            elif line == 'providers':
                pass
            else:
                print("Unknown SHOW command: %s" % line)
        except Exception as exc:
            print('ERROR:', exc)
    def complete_show(self, text: str, line: str, begidx: int, endidx: int) -> List:
        """Command completion for SHOW command."""
        if not text:
            completions = self.__show_completion[:]
        else:
            completions = [f for f in self.__show_completion if f.startswith(text)]
        return completions
    def do_start(self, line: str) -> bool:
        """Start service.

Format:
    START <service_uid> [PROCESS] [<endpoint>, [<endpoint>]]
"""
        if not self.node.is_connected():
            print("Satunin node not attached.")
            return
        if ' ' in line:
            args = line.split()
            agent_spec = args.pop(0)
        else:
            agent_spec = line
            args = []
        try:
            uid = UUID(agent_spec)
        except ValueError:
            uid = self.get_service_uid(agent_spec)
            if not uid:
                print("Service '%s' not installed." % agent_spec)
                return
        if args and args[0] == 'process':
            mode = ExecutionMode.PROCESS
            args.pop(0)
        else:
            mode = ExecutionMode.THREAD
        try:
            reply = self.node.start_service(uid, args, mode)
            table = []
            table.append(['peer uid', UUID(bytes=reply.peer_uid)])
            table.append(['mode', pb.StartModeEnum.Name(reply.mode)])
            table.append(['endpoints', '\n'.join(reply.endpoints)])
            print("Service started:")
            print(tabulate(table, tablefmt="grid"))
        except Exception as exc:
            print('ERROR:', exc)
    def complete_start(self, text: str, line: str, begidx: int, endidx: int) -> List:
        """Command completion for START command."""
        completions = [str(x) for x in self.__seen_agents]
        if text:
            completions = [x for x in completions if x.startswith(text)]
        return completions
    def do_stop(self, line: str) -> bool:
        """Stop running service.

Format:
    STOP <service_uid>
"""
        if not self.node.is_connected():
            print("Satunin node not attached.")
            return
        try:
            uid = UUID(line)
        except ValueError:
            uid = self.get_peer_uid(line)
            if not uid:
                print("Service '%s' is not running." % line)
                return
        try:
            reply = self.node.stop_service(uid)
            print(StateEnum.Name(reply))
        except Exception as exc:
            print('ERROR:', exc)
    def complete_stop(self, text: str, line: str, begidx: int, endidx: int) -> List:
        """Command completion for STOP command."""
        completions = [str(x) for x in self.__seen_peers]
        if text:
            completions = [x for x in completions if x.startswith(text)]
        return completions
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
    #def do_eof(self, line: str) -> bool:
        #"End of input"
        #return True
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
    parser.add_argument('-e', '--endpoint', help="ZMQ addresses of the Saturnin node")
    parser.add_argument('-l', '--log-level', action=UpperAction,
                        choices=[x.lower() for x in logging._nameToLevel
                                 if isinstance(x, str)],
                        help="Logging level")
    parser.set_defaults(log_level='ERROR')
    args = parser.parse_args()
    logger = logging.getLogger()
    logger.setLevel(args.log_level)

    console = NodeConsole(args)
    try:
        console.cmdloop(into)
    except KeyboardInterrupt:
        pass
    finally:
        console.finalize()

if __name__ == '__main__':
    main()
