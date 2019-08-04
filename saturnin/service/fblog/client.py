#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Firebird log service
# FILE:           saturnin/service/fblog/client.py
# DESCRIPTION:    Firebird log service client (classic version)
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

"""Firebird log service client (classic version)
"""

from typing import Dict
#from uuid import UUID
from saturnin.sdk.types import InterfaceDescriptor
from saturnin.sdk.fbsp import Session, MsgType, bb2h, ReplyMessage, ErrorMessage, exception_for
from saturnin.sdk.client import ServiceClient
from . import fblog_pb2 as pb
from .api import FbLogRequest, SERVICE_INTERFACE

class FirebirdLogClient(ServiceClient):
    """Message handler for Firebird log client."""
    def get_interface(self) -> InterfaceDescriptor:
        return SERVICE_INTERFACE
    def get_handlers(self, api_number: int) -> Dict:
        return {(MsgType.REPLY, bb2h(api_number, FbLogRequest.MONITOR)):
                self.on_monitor,
                (MsgType.REPLY, bb2h(api_number, FbLogRequest.STOP_MONITOR)):
                self.on_stop_monitor,
                (MsgType.REPLY, bb2h(api_number, FbLogRequest.ENTRIES)):
                self.on_entries,
               }
    def on_error(self, session: Session, msg: ErrorMessage):
        "Handle ERROR message received from Service."
        self.last_token_seen = msg.token
        if msg.token != session.greeting.token:
            session.request_done(msg.token)
        raise exception_for(msg)
    def on_monitor(self, session: Session, msg: ReplyMessage):
        "MONITOR reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        #dframe = pb.ReplyInstalledServices()
        #dframe.ParseFromString(msg.data.pop(0))
        #req.response = dframe
        session.request_done(req)
    def on_stop_monitor(self, session: Session, msg: ReplyMessage):
        "STOP_MONITOR reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        #dframe = pb.ReplyInstalledServices()
        #dframe.ParseFromString(msg.data.pop(0))
        #req.response = dframe
        session.request_done(req)
    def on_entries(self, session: Session, msg: ReplyMessage):
        "ENTRIES reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        #dframe = pb.ReplyRunningServices()
        #dframe.ParseFromString(msg.data.pop(0))
        #req.response = dframe
        session.request_done(req)
    # Firebird log API for clients
    def monitor(self, **kwargs) -> pb.ReplyMonitor:
        """
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               FbLogRequest.MONITOR, token)
        session.note_request(msg)
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to MONITOR request")
        return msg.response
    def stop_monitor(self, **kwargs) -> None:
        """
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               FbLogRequest.STOP_MONITOR, token)
        session.note_request(msg)
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to STOP_MONITOR request")
        return msg.response
    def get_entries(self, **kwargs) -> None:
        """
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               FbLogRequest.ENTRIES, token)
        session.note_request(msg)
        #dframe = pb.RequestInterfaceProviders()
        #dframe.interface_uid = interface_uid.bytes
        #msg.data.append(dframe.SerializeToString())
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to ENTRIES request")
        return msg.response
