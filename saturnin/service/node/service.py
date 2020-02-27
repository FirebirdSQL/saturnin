#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Runtime node service
# FILE:           saturnin/service/node/service.py
# DESCRIPTION:    Saturnin runtime node service (classic version)
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

"""Saturnin - Runtime node service (classic version)

NODE Service manages Saturnin runtime node. It provides environment for execution and
management of other Saturnin services.

Supported requests:

    :INSTALLED_SERVICES:  REPLY with list of installed services available for execution on the node.
    :RUNNING_SERVICES:    REPLY with list of services actually running on the node.
    :INTERFACE_PROVIDERS: REPLY with list of services that provide specified interface.
    :START_SERVICE:       Start service on node. REPLY with service instance information.
    :STOP_SERVICE:        Stop service running on node. REPLY with stop state.
    :SHUTDOWN:            Shuts down the NODE service.
"""

import logging
import typing as t
from uuid import UUID
from pkg_resources import iter_entry_points
from firebird.butler.fbsd_pb2 import STATE_STOPPED, STATE_TERMINATED, STATE_UNKNOWN, \
     STATE_RUNNING
from saturnin.core.types import ExecutionMode, DependencyType, AddressDomain, ZMQAddress, \
     ZMQAddressList, ServiceFacilities, ServiceDescriptor, ServiceError, SaturninError
from saturnin.core.collections import Registry
from saturnin.core.protocol.fbsp import fbsp_proto, MsgType, ErrorCode, Session, \
     ServiceMessagelHandler, HelloMessage, CancelMessage, RequestMessage, bb2h
from saturnin.core.service import TEvent, BaseService, SimpleServiceImpl
from saturnin.core.classic import ServiceExecutor
from . import node_pb2 as pb
from .api import NodeRequest, NodeError

# Logger

log = logging.getLogger(__name__)

# Constants

DEFAULT_TIMEOUT = 10000

DescriptorList = t.List[ServiceDescriptor]

# Functions

def get_best_endpoint(endpoints: ZMQAddressList,
                      client_mode: ExecutionMode = ExecutionMode.PROCESS,
                      service_mode: ExecutionMode = ExecutionMode.PROCESS) -> t.Optional[ZMQAddress]:
    """Returns endpoint address that uses the best protocol from available options, or None
if there is no address that could be used.
"""
    if endpoints is None:
        return None
    if client_mode == ExecutionMode.ANY:
        client_mode = ExecutionMode.THREAD
    if service_mode == ExecutionMode.ANY:
        service_mode = ExecutionMode.THREAD
    inproc = [x for x in endpoints if x.domain == AddressDomain.LOCAL]
    if (inproc and client_mode == ExecutionMode.THREAD and service_mode == ExecutionMode.THREAD):
        return inproc[0]
    ipc = [x for x in endpoints if x.domain == AddressDomain.NODE]
    if ipc:
        return ipc[0]
    tcp = [x for x in endpoints if x.domain == AddressDomain.NETWORK]
    return tcp[0] if tcp else None

# Classes

class SaturninNodeMessageHandler(ServiceMessagelHandler):
    """Message handler for Saturnin NODE service."""
    RQ_INSTALLED_SERVICES = bb2h(1, NodeRequest.INSTALLED_SERVICES)
    RQ_RUNNING_SERVICES = bb2h(1, NodeRequest.RUNNING_SERVICES)
    RQ_INTERFACE_PROVIDERS = bb2h(1, NodeRequest.INTERFACE_PROVIDERS)
    RQ_START_SERVICE = bb2h(1, NodeRequest.START_SERVICE)
    RQ_STOP_SERVICE = bb2h(1, NodeRequest.STOP_SERVICE)
    RQ_SHUTDOWN = bb2h(1, NodeRequest.SHUTDOWN)
    def __init__(self, welcome_df: fbsp_proto.FBSPWelcomeDataframe, impl: SimpleServiceImpl):
        super().__init__()
        self.impl: SaturninNodeServiceImpl = impl
        self.welcome_df = welcome_df
        # Our message handlers
        self.handlers.update({(MsgType.REQUEST, self.RQ_INSTALLED_SERVICES): self.handle_installed,
                              (MsgType.REQUEST, self.RQ_RUNNING_SERVICES): self.handle_running,
                              (MsgType.REQUEST, self.RQ_INTERFACE_PROVIDERS): self.handle_providers,
                              (MsgType.REQUEST, self.RQ_START_SERVICE): self.handle_start,
                              (MsgType.REQUEST, self.RQ_STOP_SERVICE): self.handle_stop,
                              (MsgType.REQUEST, self.RQ_SHUTDOWN): self.handle_shutdown,
                              MsgType.DATA: self.send_protocol_violation,
                             })
    def set_running_info(self, run_info: pb.RunningService, svc: ServiceExecutor) -> None:
        "Fill RunningService protobuf from ServiceExecutor information."
        # Peer
        run_info.peer.uid = svc.peer.uid.bytes
        run_info.peer.pid = svc.peer.pid
        run_info.peer.host = svc.peer.host
        # Agent
        run_info.agent.uid = svc.descriptor.agent.uid.bytes
        run_info.agent.name = svc.descriptor.agent.name
        run_info.agent.version = svc.descriptor.agent.version
        run_info.agent.vendor.uid = svc.descriptor.agent.vendor_uid.bytes
        run_info.agent.platform.uid = svc.descriptor.agent.platform_uid.bytes
        run_info.agent.platform.version = svc.descriptor.agent.platform_version
        run_info.agent.classification = svc.descriptor.agent.classification
        # Rest
        run_info.description = svc.descriptor.description
        run_info.mode = svc.mode.value
        for flag in svc.facilities.get_flags():
            if flag == ServiceFacilities.FBSP_SOCKET:
                run_info.facilities.append(pb.SVC_FACILITY_FBSP_SOCKET)
            elif flag == ServiceFacilities.INPUT_SERVER:
                run_info.facilities.append(pb.SVC_FACILITY_INPUT_SERVER)
            elif flag == ServiceFacilities.INPUT_CLIENT:
                run_info.facilities.append(pb.SVC_FACILITY_INPUT_CLIENT)
            elif flag == ServiceFacilities.OUTPUT_SERVER:
                run_info.facilities.append(pb.SVC_FACILITY_OUTPUT_SERVER)
            elif flag == ServiceFacilities.OUTPUT_CLIENT:
                run_info.facilities.append(pb.SVC_FACILITY_OUTPUT_CLIENT)
        svc.config.save_proto(run_info.config)
        if svc.endpoints:
            run_info.endpoints.extend(svc.endpoints)
    def handle_hello(self, session: Session, msg: HelloMessage):
        "HELLO message handler. Sends WELCOME message back to the client."
        if __debug__:
            log.debug("%s.handle_hello(%s)", self.__class__.__name__, session.routing_id)
        super().handle_hello(session, msg)
        welcome = self.protocol.create_welcome_reply(msg)
        welcome.peer.CopyFrom(self.welcome_df)
        self.send(welcome, session)
    def handle_cancel(self, session: Session, msg: CancelMessage):
        "Handle CANCEL message."
        # NODE uses simple REQUEST/REPLY API, so there is no point to send CANCEL
        # messages. However, we have to handle it although we'll do nothing.
        # In such cases we could either override the on_cancel() method like now,
        # or assign self.do_nothing handler to MsgType.CANCEL in __init__().
        log.debug("%s.on_cancel(%s)", self.__class__.__name__, session.routing_id)
    def handle_installed(self, session: Session, msg: RequestMessage):
        """Handle REQUEST/INSTALLED_SERVICES message.
"""
        log.debug("%s.on_installed(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply data frame
        dframe = pb.ReplyInstalledServices()
        for svc_desc in (svc for svc in self.impl.installed_services):
            svc_data = dframe.services.add()
            # Agent
            svc_data.agent.uid = svc_desc.agent.uid.bytes
            svc_data.agent.name = svc_desc.agent.name
            svc_data.agent.version = svc_desc.agent.version
            svc_data.agent.vendor.uid = svc_desc.agent.vendor_uid.bytes
            svc_data.agent.platform.uid = svc_desc.agent.platform_uid.bytes
            svc_data.agent.platform.version = svc_desc.agent.platform_version
            svc_data.agent.classification = svc_desc.agent.classification
            # API
            for api in svc_desc.api:
                api_pb = svc_data.api.add()
                api_pb.uid = api.uid.bytes
                api_pb.name = api.name
                api_pb.revision = api.revision
                api_pb.number = api.number
                # Request codes
                for rcode in api.requests:
                    rc_pb = api_pb.requests.add()
                    rc_pb.code = rcode.value
                    rc_pb.name = rcode.name
            # Dependencies
            for d_type, d_uid in svc_desc.dependencies:
                d_pb = svc_data.dependencies.add()
                d_pb.type = d_type.value
                d_pb.uid = d_uid.bytes
            #
            svc_data.service_type = svc_desc.service_type
            svc_data.description = svc_desc.description
            svc_data.mode = svc_desc.execution_mode
            for flag in svc_desc.facilities.get_flags():
                if flag == ServiceFacilities.FBSP_SOCKET:
                    svc_data.facilities.append(pb.SVC_FACILITY_FBSP_SOCKET)
                elif flag == ServiceFacilities.INPUT_SERVER:
                    svc_data.facilities.append(pb.SVC_FACILITY_INPUT_SERVER)
                elif flag == ServiceFacilities.INPUT_CLIENT:
                    svc_data.facilities.append(pb.SVC_FACILITY_INPUT_CLIENT)
                elif flag == ServiceFacilities.OUTPUT_SERVER:
                    svc_data.facilities.append(pb.SVC_FACILITY_OUTPUT_SERVER)
                elif flag == ServiceFacilities.OUTPUT_CLIENT:
                    svc_data.facilities.append(pb.SVC_FACILITY_OUTPUT_CLIENT)
        reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def handle_running(self, session: Session, msg: RequestMessage):
        """Handle REQUEST/RUNNING_SERVICES message.
"""
        log.debug("%s.on_running(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        dframe = pb.ReplyRunningServices()
        for svc in self.impl.services:
            svc: ServiceExecutor
            if svc.is_running():
                self.set_running_info(dframe.services.add(), svc)
        reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def handle_providers(self, session: Session, msg: RequestMessage):
        """Handle REQUEST/INTERFACE_PROVIDERS message.
"""
        log.debug("%s.on_providers(%s)", self.__class__.__name__, session.routing_id)
        dframe = pb.RequestInterfaceProviders()
        dframe.ParseFromString(msg.data[0])
        interface_uid = dframe.interface_uid
        # create reply
        reply = self.protocol.create_reply_for(msg)
        dframe = pb.ReplyInterfaceProviders()
        for svc_desc in self.impl.get_providers(interface_uid):
            dframe.agent_uids.append(svc_desc.agent.uid.bytes)
        reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def handle_start(self, session: Session, msg: RequestMessage):
        """Handle REQUEST/START_SERVICE message.
"""
        if __debug__: log.debug("%s.on_start(%s)", self.__class__.__name__, session.routing_id)
        dframe: pb.RequestStartService = pb.RequestStartService()
        dframe.ParseFromString(msg.data[0])
        agent_uid = UUID(bytes=dframe.agent_uid)
        agent: ServiceDescriptor = self.impl.installed_services.get(agent_uid)
        if agent is None:
            self.send_error(session, msg, ErrorCode.NOT_FOUND, "Service not found")
            return
        #
        if self.impl.is_running(agent_uid) and dframe.singleton:
            reply = self.protocol.create_reply_for(msg)
            dframe = pb.ReplyStartService()
            svc = self.impl.get_running(agent_uid)
            if svc:
                self.set_running_info(dframe.service, svc)
                reply.data.append(dframe.SerializeToString())
                self.send(reply, session)
                return
        #
        try:
            svc: ServiceExecutor = self.impl.add_service(agent)
        except ServiceError as exc:
            self.send_error(session, msg, ErrorCode.ERROR, "Service start failed",
                            app_code=NodeError.START_FAILED, exc=exc)
            return
        if dframe.name:
            svc.name = dframe.name
        cfg = svc.descriptor.config()
        cfg.load_proto(dframe.config)
        try:
            if dframe.timeout > 0:
                svc.start(cfg, timeout=dframe.timeout)
            else:
                svc.start(cfg)
        except TimeoutError:
            self.send_error(session, msg, ErrorCode.REQUEST_TIMEOUT, "Service start failed")
            return
        except ServiceError as exc:
            self.send_error(session, msg, ErrorCode.ERROR, "Service start failed",
                            app_code=NodeError.START_FAILED, exc=exc)
            return
        # reply
        reply = self.protocol.create_reply_for(msg)
        dframe = pb.ReplyStartService()
        self.set_running_info(dframe.service, svc)
        reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def handle_stop(self, session: Session, msg: RequestMessage):
        """Handle REQUEST/STOP_SERVICE message.
"""
        log.debug("%s.on_stop(%s)", self.__class__.__name__, session.routing_id)
        dframe: pb.RequestStopService = pb.RequestStopService()
        dframe.ParseFromString(msg.data[0])
        peer_uid = UUID(bytes=dframe.peer_uid)
        svc: ServiceExecutor = self.impl.services.get(peer_uid)
        if svc is None:
            self.send_error(session, msg, ErrorCode.NOT_FOUND, "Service is not running")
            return
        #
        rframe: pb.ReplyStopService = pb.ReplyStopService()
        rframe.result = STATE_UNKNOWN
        try:
            if dframe.timeout > 0:
                svc.stop(dframe.timeout / 1000)
            else:
                svc.stop()
            rframe.result = STATE_STOPPED
        except TimeoutError:
            if not dframe.forced:
                self.send_error(session, msg, ErrorCode.REQUEST_TIMEOUT,
                                "Failed to stop service",
                                app_code=NodeError.TERMINATION_FAILED)
                return
        except ServiceError as exc:
            if not dframe.forced:
                self.send_error(session, msg, ErrorCode.ERROR, "Failed to stop service",
                                app_code=NodeError.TERMINATION_FAILED, exc=exc)
                return
        if rframe.result == STATE_UNKNOWN:
            try:
                svc.terminate()
                rframe.result = STATE_TERMINATED
            except SaturninError as exc:
                self.send_error(session, msg, ErrorCode.ERROR,
                                "Service termination has failed",
                                app_code=NodeError.TERMINATION_FAILED, exc=exc)
                return
        #
        if svc.is_running():
            rframe.result = STATE_RUNNING
        else:
            self.impl.services.remove(svc)
        #
        reply = self.protocol.create_reply_for(msg)
        reply.data.append(rframe.SerializeToString())
        self.send(reply, session)
    def handle_shutdown(self, session: Session, msg: RequestMessage):
        """Handle REQUEST/SHUTDOWN message.
"""
        log.debug("%s.on_shutdown(%s)", self.__class__.__name__, session.routing_id)
        # send reply to confirm that shutdown was initiated
        reply = self.protocol.create_reply_for(msg)
        self.send(reply, session)
        # commence shutdown
        self.impl.stop_event.set()

class SaturninNodeServiceImpl(SimpleServiceImpl):
    """Implementation of Saturnin NODE service."""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: TEvent):
        super().__init__(descriptor, stop_event)
        self.installed_services: Registry = Registry()
        self.services: Registry = Registry()
    def initialize(self, svc: BaseService):
        super().initialize(svc)
        self.svc_chn.set_handler(SaturninNodeMessageHandler(self.welcome_df, self))
        # Load information about installed services.
        self.installed_services.extend(entry.load() for entry in
                                       iter_entry_points('saturnin.service'))
    def finalize(self, svc: BaseService) -> None:
        """Service finalization. Stops/terminates all services running on node.
"""
        log.debug("%s.finalize", self.__class__.__name__)
        for svc in self.services:
            svc: ServiceExecutor
            try:
                svc.stop()
            except:
                try:
                    log.warning("Service did not stop on time - terminating, peer[%s:%s] agent[%s:%s]",
                                svc.uid, svc.name, svc.agent_uid, svc.agent_name)
                    svc.terminate()
                except:
                    log.exception("Service termination has failed, peer[%s:%s] agent[%s:%s]",
                                  svc.uid, svc.name, svc.agent_uid, svc.agent_name)
        super().finalize(svc)
    def on_idle(self) -> None:
        """Called by service when waiting for messages exceeds timeout. Performs check
for running services. Dead services are removed from list of running services.
"""
        for svc in self.services:
            if not svc.is_running():
                log.info("The service ended itself, peer[%s:%s] agent[%s:%s]",
                         svc.uid, svc.name, svc.agent_uid, svc.agent_name)
                self.services.remove(svc)
    def get_service_descriptor(self, agent_uid: UUID) -> ServiceDescriptor:
        """Returns descriptor for installed service.

Raises:
    :ValueError: If service is not installed.
"""
        return self.installed_services.get(agent_uid)
    def get_providers(self, interface_uid: bytes) -> DescriptorList:
        """Returns list of ServiceDescriptors of services that implement interface."""
        result = []
        for svc_desc in self.installed_services:
            for api in svc_desc.api:
                if api.uid.bytes == interface_uid:
                    result.append(svc_desc)
        return result
    def get_running_providers(self, interface_uid: bytes) -> DescriptorList:
        """Returns list of ServiceDescriptors of services that implement interface."""
        result = []
        for svc in self.services:
            svc: ServiceExecutor
            for api in svc.descriptor.api:
                if api.uid.bytes == interface_uid:
                    result.append(svc.descriptor)
        return result
    def add_service(self, svc_descriptor: ServiceDescriptor) -> ServiceExecutor:
        """Create and return new `ServiceExecutor`.

Raises:
    :ServiceError: If the service has declared the required dependencies that are not running.
"""
        def find_provider_address(interface_uid):
            for provider in self.get_running_providers(interface_uid.bytes):
                provider: ServiceExecutor
                for svc in self.services:
                    if svc.agent_uid == provider.agent_uid:
                        return get_best_endpoint(svc.endpoints, provider.mode, svc.mode)
            return None

        # Find endpoints to running dependencies
        svc = ServiceExecutor(svc_descriptor)
        for dtype, interface_uid in svc_descriptor.dependencies:
            if dtype == DependencyType.REQUIRED:
                if find_provider_address(interface_uid) is None:
                    raise ServiceError("Provider not available for required interface %s"
                                       % interface_uid)
        self.services.store(svc)
        return svc
    def get_running(self, agent_uid: UUID) -> bool:
        """Returns True if service is running."""
        for svc in self.services:
            if svc.agent_uid == agent_uid:
                if svc.is_running():
                    return svc
        return None
    def is_running(self, agent_uid: UUID) -> bool:
        """Returns True if service is running."""
        for svc in self.services:
            if svc.agent_uid == agent_uid:
                if svc.is_running():
                    return True
        return False
