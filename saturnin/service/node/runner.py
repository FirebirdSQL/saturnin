#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Runtime node service executor
# FILE:           saturnin/service/node/runner.py
# DESCRIPTION:    Script that runs Saturnin NODE service
# CREATED:        17.5.2019
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

"""Saturnin - Runtime node service executor

NODE Service manages Saturnin runtime node. It provides environment for execution and
management of other Saturnin services. This script is a simple initial runner for testing
purposes. It will be replaced with daemon (POSIX) / service (Windows) runners.
"""

import logging
from typing import Dict, List, Optional
import signal
from uuid import UUID, uuid1
from os import getpid
import socket
import platform
from argparse import ArgumentParser, Action
from saturnin.sdk.types import PeerDescriptor
from saturnin.sdk.base import load, DummyEvent
from saturnin.service.node.api import SERVICE_DESCRIPTION

__VERSION__ = '0.1'

# Classes

class UpperAction(Action):
    "Converts argument to uppercase."
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

def main():
    "Main function"

    def handle_signal(signum, frame):
        if signum == signal.SIGINT:
            print("\nTerminating on user request...")
        else:
            print("\nTerminating...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    stop_event = DummyEvent()
    node_uid = uuid1()
    node_endpoints = ['inproc://%s' % node_uid.hex]
    if platform.system == 'Linux':
        node_endpoints.append('ipc://@%s' % node_uid.hex)
    else:
        node_endpoints.append('tcp://127.0.0.1:*')
    description = """Saturnin NODE runner."""
    parser = ArgumentParser(description=description)
    parser.add_argument('-e', '--endpoint', nargs='+', help="ZMQ addresses for the service")
    parser.add_argument('-l', '--log-level', action=UpperAction,
                        choices=[x.lower() for x in logging._nameToLevel
                                 if isinstance(x, str)],
                        help="Logging level")
    parser.set_defaults(log_level='ERROR', endpoint=node_endpoints)
    args = parser.parse_args()
    logger = logging.getLogger()
    logger.setLevel(args.log_level)

    node_implementation = load(SERVICE_DESCRIPTION.implementation)(stop_event)
    node_implementation.endpoints = args.endpoint
    node_implementation.peer = PeerDescriptor(node_uid, getpid(), socket.getfqdn())
    node_service = load(SERVICE_DESCRIPTION.container)(node_implementation)
    node_service.initialize()
    try:
        args = parser.parse_args()
        print(f"Saturnin node runner v{__VERSION__}")
        for addr in node_service.impl.endpoints:
            print(f"Node address: {addr}")
        node_service.start()
    except Exception as exc:
        logger.exception("Fatal exception, node terminated.")
    logging.shutdown()
    print('Done.')

if __name__ == '__main__':
    main()
