#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Firebird log service
# FILE:           saturnin/service/fblog/service.py
# DESCRIPTION:    Firebird log service (classic version)
# CREATED:        3.6.2019
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

"""Firebird log service (classic version)

Firebird log Service monitors firebird.log file and emits log events into data pipeline.

Supported requests:

    :MONITOR:     Starts contionuous monitoring of firebird.log file. New entries are parsed
                  and sent to data pipeline.
    :GET_ENTRIES: Send parsed (selected) entries from firebird.log as stream of DATA messages.
"""

import logging
from typing import Any
#from uuid import uuid1, UUID
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from saturnin.sdk.types import ServiceError, InvalidMessageError, MsgType, \
     TService, TSession, TServiceImpl, TChannel
from saturnin.sdk.base import BaseService
from saturnin.sdk.service import SimpleServiceImpl
from saturnin.sdk.fbsp import ServiceMessagelHandler, HelloMessage, \
     CancelMessage, RequestMessage, bb2h
#from saturnin.protobuf import node_pb2 as pb
from saturnin.service.fblog.api import FbLogRequest, FbLogError, SERVICE_AGENT, SERVICE_API
import fdb

# Logger

log = logging.getLogger(__name__)

# Constants

# Classes

class FirebirdLogEventHandler(FileSystemEventHandler):
    """Filesystem event handler for monitoring firebird.log"""
    def on_created(self, event):
        "Called when a file or directory is created."
    def on_deleted(self, event):
        "Called when a file or directory is deleted."
    def on_moved(self, event):
        "Called when a file or a directory is moved or renamed."
    def on_modified(self, event):
        "Called when a file or directory is modified."

class FirebirdLogMessageHandler(ServiceMessagelHandler):
    """Message handler for Firebird log service."""
    def __init__(self, chn: TChannel, service: TServiceImpl):
        super().__init__(chn, service)
        # Our message handlers
        self.handlers.update({(MsgType.REQUEST, bb2h(1, FbLogRequest.MONITOR)):
                              self.on_monitor,
                              (MsgType.REQUEST, bb2h(1, FbLogRequest.GET_ENTRIES)):
                              self.on_get_entries,
                              MsgType.DATA: self.send_protocol_violation,
                             })
    def on_hello(self, session: TSession, msg: HelloMessage):
        "HELLO message handler. Sends WELCOME message back to the client."
        log.debug("%s.on_hello(%s)", self.__class__.__name__, session.routing_id)
        super().on_hello(session, msg)
        welcome = self.protocol.create_welcome_reply(msg)
        welcome.peer.CopyFrom(self.impl.welcome_df)
        self.send(welcome, session)
    def on_cancel(self, session: TSession, msg: CancelMessage):
        "Handle CANCEL message."
        # We support CANCEL for MONITOR requests
        log.debug("%s.on_cancel(%s)", self.__class__.__name__, session.routing_id)
    def on_monitor(self, session: TSession, msg: RequestMessage):
        "Handle REQUEST/MONITOR message."
        log.debug("%s.on_monitor(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply data frame
        #dframe = pb.ReplyInstalledServices()
        #reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def on_get_entries(self, session: TSession, msg: RequestMessage):
        "Handle REQUEST/GET_ENTRIES message."
        log.debug("%s.on_get_entries(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply data frame
        #dframe = pb.ReplyInstalledServices()
        #reply.data.append(dframe.SerializeToString())
        self.send(reply, session)


class FirebirdLogServiceImpl(SimpleServiceImpl):
    """Implementation of Firebird Log service."""
    def __init__(self, stop_event: Any):
        super().__init__(stop_event)
        self.agent = SERVICE_AGENT
        self.api = SERVICE_API
    def initialize(self, svc: BaseService):
        super().initialize(svc)
        self.msg_handler = FirebirdLogMessageHandler(self.svc_chn, self)
    def finalize(self, svc: TService) -> None:
        """Service finalization. Stops/terminates all services running on node.
"""
        log.debug("%s.finalize", self.__class__.__name__)
        # Stop running requests
        super().finalize(svc)
