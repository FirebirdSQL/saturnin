#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Runtime node service
# FILE:           saturnin/service/node/client.py
# DESCRIPTION:    NODE service client (classic version)
# CREATED:        12.5.2019
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

"""Saturnin - NODE service client (classic version)

NODE Service manages Saturnin runtime node. It provides environment for execution and
management of other Saturnin services.
"""

import typing as t
from uuid import UUID
from saturnin.core.types import State, InterfaceDescriptor
from saturnin.core.config import Config
from saturnin.core.protocol.fbsp import Session, MsgType, bb2h, ReplyMessage, ErrorMessage, exception_for
from saturnin.core.client import ServiceClient
from . import node_pb2 as pb
from .api import NodeRequest, SERVICE_INTERFACE

class SaturninNodeClient(ServiceClient):
    """Message handler for NODE client."""
    def get_interface(self) -> InterfaceDescriptor:
        return SERVICE_INTERFACE
    def get_handlers(self, api_number: int) -> t.Dict:
        return {(MsgType.REPLY, bb2h(api_number, NodeRequest.INSTALLED_SERVICES)):
                self.handle_installed,
                (MsgType.REPLY, bb2h(api_number, NodeRequest.RUNNING_SERVICES)):
                self.handle_running,
                (MsgType.REPLY, bb2h(api_number, NodeRequest.INTERFACE_PROVIDERS)):
                self.handle_providers,
                (MsgType.REPLY, bb2h(api_number, NodeRequest.START_SERVICE)):
                self.handle_start,
                (MsgType.REPLY, bb2h(api_number, NodeRequest.STOP_SERVICE)):
                self.handle_stop,
                (MsgType.REPLY, bb2h(api_number, NodeRequest.SHUTDOWN)):
                self.handle_shutdown,
                MsgType.DATA: self.raise_protocol_violation,
                MsgType.REPLY: self.raise_protocol_violation,
                MsgType.STATE: self.raise_protocol_violation,
               }
    def handle_error(self, session: Session, msg: ErrorMessage):
        "Handle ERROR message received from Service."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        req.response = None
        if msg.token != session.greeting.token:
            session.request_done(req)
        raise exception_for(msg)
    def handle_installed(self, session: Session, msg: ReplyMessage):
        "INSTALLED_SERVICES reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        dframe = pb.ReplyInstalledServices()
        dframe.ParseFromString(msg.data.pop(0))
        req.response = dframe
        session.request_done(req)
    def handle_running(self, session: Session, msg: ReplyMessage):
        "RUNNING_SERVICES reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        dframe = pb.ReplyRunningServices()
        dframe.ParseFromString(msg.data.pop(0))
        req.response = dframe
        session.request_done(req)
    def handle_providers(self, session: Session, msg: ReplyMessage):
        "INTERFACE_PROVIDERS reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        dframe = pb.ReplyInterfaceProviders()
        dframe.ParseFromString(msg.data.pop(0))
        req.response = [UUID(bytes=uid) for uid in dframe.agent_uids]
        session.request_done(req)
    def handle_start(self, session: Session, msg: ReplyMessage):
        "START_SERVICE reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        dframe = pb.ReplyStartService()
        dframe.ParseFromString(msg.data.pop(0))
        req.response = dframe
        session.request_done(req)
    def handle_stop(self, session: Session, msg: ReplyMessage):
        "STOP_SERVICE reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        dframe = pb.ReplyStopService()
        dframe.ParseFromString(msg.data.pop(0))
        req.response = State(dframe.result)
        session.request_done(req)
    def handle_shutdown(self, session: Session, msg: ReplyMessage):
        "SHUTDOWN reply handler."
        self.last_token_seen = msg.token
        req = session.get_request(msg.token)
        req.response = True
        session.request_done(req)
    # Saturnin NODE API for clients
    def get_installed(self, **kwargs) -> pb.ReplyInstalledServices:
        """Get list of services installed on Saturnin node.

Returns:
    List of services installed on node.
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.INSTALLED_SERVICES, token)
        session.note_request(msg)
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to INSTALLED_SERVICES request")
        return msg.response
    def get_running(self, **kwargs) -> pb.ReplyRunningServices:
        """Get list of services running on Saturnin node.

Returns:
    List of services running on node.
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.RUNNING_SERVICES, token)
        session.note_request(msg)
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to RUNNING_SERVICES request")
        return msg.response
    def get_providers(self, interface_uid: UUID, **kwargs) -> t.List[UUID]:
        """Get list of services that provider specified interface.

Returns:
    List of service UIDs.
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.INTERFACE_PROVIDERS, token)
        session.note_request(msg)
        dframe = pb.RequestInterfaceProviders()
        dframe.interface_uid = interface_uid.bytes
        msg.data.append(dframe.SerializeToString())
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to INTERFACE_PROVIDERS request")
        return msg.response
    def start_service(self, agent_uid: UUID, config: Config,
                      name: str = None,
                      start_timeout: int = None,
                      singleton: bool = False, **kwargs) -> pb.ReplyStartService:
        """Starts specified service.

Returns:
    Details about started service.
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.START_SERVICE, token)
        session.note_request(msg)
        dframe: pb.RequestStartService = pb.RequestStartService()
        dframe.agent_uid = agent_uid.bytes
        config.save_proto(dframe.config)
        if name:
            dframe.name = name
        if start_timeout:
            dframe.timeout = start_timeout
        dframe.singleton = singleton
        msg.data.append(dframe.SerializeToString())
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to START_SERVICE request")
        return msg.response
    def stop_service(self, peer_uid: UUID, stop_timeout: int = None, forced: bool = False,
                      **kwargs) -> pb.ReplyStopService:
        """Starts specified service.

Returns:
    Details about started service.
"""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.STOP_SERVICE, token)
        session.note_request(msg)
        dframe = pb.RequestStopService()
        dframe.peer_uid = peer_uid.bytes
        if stop_timeout:
            dframe.timeout = stop_timeout
        dframe.forced = forced
        msg.data.append(dframe.SerializeToString())
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to STOP_SERVICE request")
        return msg.response
    def shutdown(self, **kwargs) -> True:
        """Stops the Saturnin node."""
        session: Session = self.get_session()
        assert session
        token = self.new_token()
        msg = self.protocol.create_request_for(self.interface_id,
                                               NodeRequest.SHUTDOWN, token)
        session.note_request(msg)
        self.send(msg)
        if not self.get_response(token, kwargs.get('timeout')):
            raise TimeoutError("The service did not respond on time to SHUTDOWN request")
        return msg.response
