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
    :START_SERVICE:       Start service on node.
    :STOP_SERVICE:        Stop service running on node.
    :REQUEST_PROVIDER:    REPLY with address for most efficient connection to the servie
                          that provides specified interface. Starts the service if necessary.
    :SHUTDOWN:            Shuts down the NODE service.
"""

import logging
from typing import Any, Optional, Dict
from uuid import uuid1, UUID
from os import getpid
import ctypes
import platform
import threading
import multiprocessing
import zmq
from pkg_resources import iter_entry_points
from saturnin.sdk.types import SaturninError, ServiceError, InvalidMessageError, MsgType, \
     ErrorCode, TService, TSession, TServiceImpl, TChannel, ZMQAddressList, PeerDescriptor, \
     ServiceDescriptor, ExecutionMode
from saturnin.service.node.api import SaturninNodeRequest, SERVICE_AGENT, SERVICE_API, \
     NODE_INTERFACE_UID
from saturnin.sdk.base import BaseChannel, BaseService, load
from saturnin.sdk.service import SimpleServiceImpl
from saturnin.sdk.fbsp import ServiceMessagelHandler, HelloMessage, \
     CancelMessage, RequestMessage, bb2h
from saturnin.protobuf import node_pb2 as pb

# Logger

log = logging.getLogger(__name__)

# Constants

START_TIMEOUT = 5000

# Functions

def protocol_name(address: str) -> str:
    "Returns protocol name from address."
    return address.split(':', 1)[0].lower()

def get_best_endpoint(endpoints, client_mode=ExecutionMode.PROCESS,
                      service_mode=ExecutionMode.PROCESS) -> Optional[str]:
    "Returns endpoint that uses the best protocol from available options."
    inproc = [x for x in endpoints if protocol_name(x) == 'inproc']
    if (inproc and client_mode == ExecutionMode.THREAD and service_mode == ExecutionMode.THREAD):
        return inproc[0]
    ipc = [x for x in endpoints if protocol_name(x) == 'ipc']
    if ipc:
        return ipc[0]
    tcp = [x for x in endpoints if protocol_name(x) == 'tcp']
    return tcp[0]

def service_run(peer_uid: UUID, endpoints: ZMQAddressList, svc_descriptor: ServiceDescriptor,
                stop_event: Any, remotes: Dict[bytes, str], ctrl_addr: bytes):
    "Process or thread target code to run the service."
    ctx = zmq.Context.instance()
    pipe = ctx.socket(zmq.DEALER)
    pipe.IMMEDIATE = 1
    pipe.connect(ctrl_addr)
    #
    try:
        svc_implementation = load(svc_descriptor.implementation)
        svc_class = load(svc_descriptor.container)
        svc_impl = svc_implementation(stop_event)
        svc_impl.endpoints = endpoints
        svc_impl.peer = PeerDescriptor(peer_uid, getpid(), platform.node())
        svc = svc_class(svc_impl)
        svc.remotes = remotes.copy()
        svc.initialize()
        pipe.send_pyobj(0)
        pipe.send_pyobj(svc_impl.endpoints)
        pipe.send_pyobj(svc_impl.peer)
        pipe.close()
        svc.start()
    except Exception as exc:
        if not pipe.closed():
            pipe.send_pyobj(1)
            pipe.send_pyobj(exc)
            pipe.close()

# Classes

class NodeService:
    """Service managed by saturnin node.

Attributes:
    :uid:        Peer UID.
    :name:       Service name.
    :endpoints:  List of service endpoints.
    :descriptor: Service descriptor.
    :mode:       Service execution mode.
    :remotes:    Dictionary that maps interface ID to service address.
    :runtime:    None, or threading.Thread or multiprocessing.Process instance.
"""
    def __init__(self, svc_descriptor: ServiceDescriptor,
                 mode: ExecutionMode = ExecutionMode.ANY):
        self.__peer_uid = uuid1()
        self.endpoints: ZMQAddressList = []
        self.endpoints.append('inproc://%s' % self.uid.hex)
        if platform.system == 'Linux':
            self.endpoints.append('ipc://@%s' % self.uid.hex)
        else:
            self.endpoints.append('tcp://127.0.0.1:*')
        self.descriptor: ServiceDescriptor = svc_descriptor
        if mode != ExecutionMode.ANY:
            self.mode = mode
        elif svc_descriptor.execution_mode != ExecutionMode.ANY:
            self.mode = svc_descriptor.execution_mode
        else:
            self.mode = ExecutionMode.THREAD
        self.remotes: Dict[bytes, str] = {}
        self.runtime = None
        self.peer: Optional[PeerDescriptor] = None
    def is_running(self) -> bool:
        """Returns True if service is running."""
        if self.runtime is None:
            return False
        if self.runtime.is_alive():
            return True
        # It's dead, so dispose the runtime
        self.runtime = None
        return False
    def start(self, endpoints: ZMQAddressList, timeout=START_TIMEOUT):
        """Start the service.

If `mode` is ANY or THREAD, the service is executed in it's own thread. Otherwise it is
executed in separate child process.

Arguments:
    :timeout: The timeout (in milliseconds) to wait for service to start [Default: 5000].

Raises:
    :SaturninError: The service is already running.
    :TimeoutError:  The service did not start on time.
"""
        if self.is_running():
            raise SaturninError("The service is already running")
        ctx = zmq.Context.instance()
        pipe = ctx.socket(zmq.DEALER)
        uid = bytes(uuid1().hex, 'ascii')
        try:
            if self.mode in (ExecutionMode.ANY, ExecutionMode.THREAD):
                addr = b'inproc://%s' % uid
                pipe.bind(addr)
                self.ready_event = threading.Event()
                self.stop_event = threading.Event()
                self.runtime = threading.Thread(target=service_run, name=self.name,
                                                args=(self.uid, self.endpoints,
                                                      self.descriptor,
                                                      self.stop_event, self.remotes, addr))
            else:
                if platform.system == 'Linux':
                    addr = b'ipc://@%s' % uid
                else:
                    self.endpoints.append(b'tcp://127.0.0.1:*')
                pipe.bind(addr)
                addr = pipe.LAST_ENDPOINT
                self.ready_event = multiprocessing.Event()
                self.stop_event = multiprocessing.Event()
                self.runtime = multiprocessing.Process(target=service_run, name=self.name,
                                                       args=(self.uid, self.endpoints,
                                                             self.descriptor,
                                                             self.stop_event, self.remotes,
                                                             addr))
            self.runtime.start()
            if pipe.poll(timeout, zmq.POLLIN) == 0:
                raise TimeoutError("The service did not start on time")
            else:
                msg = pipe.recv_pyobj()
                if msg == 0: # OK
                    msg = pipe.recv_pyobj()
                    self.endpoints = msg
                    msg = pipe.recv_pyobj()
                    self.peer = msg
                else: # Exception
                    msg = pipe.recv_pyobj()
                    raise ServiceError("Service start failed") from msg
        finally:
            pipe.LINGER = 0
            pipe.close()
    def stop(self, timeout=None):
        """Stop the service. Does nothing if service is not running.

Arguments:
    :timeout: None (infinity), or a floating point number specifying a timeout for
              the operation in seconds (or fractions thereof) [Default: None].

Raises:
    :TimeoutError:  The service did not stop on time.
"""
        if self.is_running():
            self.stop_event.set()
            self.runtime.join(timeout=timeout)
            if self.runtime.is_alive():
                raise TimeoutError("The service did not stop on time")
            else:
                self.runtime = None
    def terminate(self):
        """Terminate the service.

Terminate should be called ONLY when call to stop() (with sensible timeout) fails.
Does nothing when service is not running.

Raises:
    :SaturninError:  When service termination fails.
"""
        if self.is_running():
            tid = ctypes.c_long(self.runtime.ident)
            if isinstance(self.runtime, threading.Thread):
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(SystemExit))
                if res == 0:
                    raise SaturninError("Service termination failed due to invalid thread ID.")
                elif res != 1:
                    # if it returns a number greater than one, you're in trouble,
                    # and you should call it again with exc=NULL to revert the effect
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
                    raise SaturninError("Service termination failed due to PyThreadState_SetAsyncExc failure")
            elif isinstance(self.runtime, multiprocessing.Process):
                self.runtime.terminate()
            else:
                raise SaturninError("Service termination faileddue to invalid runtime.")
    uid: UUID = property(fget=lambda self: self.__peer_uid, doc="Peer ID")
    agent_uid: UUID = property(fget=lambda self: self.descriptor.agent.uid, doc="Agent ID")
    name: str = property(fget=lambda self: self.descriptor.agent.name, doc="Service name")


class SaturninNodeMessageHandler(ServiceMessagelHandler):
    """Message handler for Saturnin NODE service."""
    def __init__(self, chn: TChannel, service: TServiceImpl):
        super().__init__(chn, service)
        # Our message handlers
        self.handlers.update({(MsgType.REQUEST, bb2h(1, SaturninNodeRequest.INSTALLED_SERVICES)):
                              self.on_installed,
                              (MsgType.REQUEST, bb2h(1, SaturninNodeRequest.RUNNING_SERVICES)):
                              self.on_running,
                              (MsgType.REQUEST, bb2h(1, SaturninNodeRequest.INTERFACE_PROVIDERS)):
                              self.on_providers,
                              (MsgType.REQUEST, bb2h(1, SaturninNodeRequest.START_SERVICE)):
                              self.on_start,
                              (MsgType.REQUEST, bb2h(1, SaturninNodeRequest.STOP_SERVICE)):
                              self.on_stop,
                              (MsgType.REQUEST, bb2h(1, SaturninNodeRequest.REQUEST_PROVIDER)):
                              self.on_req_provider,
                              (MsgType.REQUEST, bb2h(1, SaturninNodeRequest.SHUTDOWN)):
                              self.on_shutdown,
                              MsgType.DATA: self.send_protocol_violation,
                             })
    def on_invalid_message(self, session: TSession, exc: InvalidMessageError):
        "Invalid Message event."
        log.error("%s.on_invalid_message(%s/%s)", self.__class__.__name__,
                  session.routing_id, exc)
        raise ServiceError("Invalid message") from exc
    def on_invalid_greeting(self, exc: InvalidMessageError):
        "Invalid Greeting event."
        log.error("%s.on_invalid_greeting(%s)", self.__class__.__name__, exc)
        raise ServiceError("Invalid Greeting") from exc
    def on_dispatch_error(self, session: TSession, exc: Exception):
        "Exception unhandled by `dispatch()`."
        log.error("%s.on_dispatch_error(%s/%s)", self.__class__.__name__,
                  session.routing_id, exc)
        raise ServiceError("Unhandled exception") from exc
    def on_hello(self, session: TSession, msg: HelloMessage):
        "HELLO message handler. Sends WELCOME message back to the client."
        log.debug("%s.on_hello(%s)", self.__class__.__name__, session.routing_id)
        super().on_hello(session, msg)
        welcome = self.protocol.create_welcome_reply(msg)
        welcome.peer.CopyFrom(self.impl.welcome_df)
        self.send(welcome, session)
    def on_cancel(self, session: TSession, msg: CancelMessage):
        "Handle CANCEL message."
        # NODE uses simple REQUEST/REPLY API, so there is no point to send CANCEL
        # messages. However, we have to handle it although we'll do nothing.
        # In such cases we could either override the on_cancel() method like now,
        # or assign self.do_nothing handler to MsgType.CANCEL in __init__().
        log.debug("%s.on_cancel(%s)", self.__class__.__name__, session.routing_id)
    def on_installed(self, session: TSession, msg: RequestMessage):
        """Handle REQUEST/INSTALLED_SERVICES message.
"""
        log.debug("%s.on_installed(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply data frame
        dframe = pb.ReplyInstalledServices()
        for svc_desc in (svc for svc in self.impl.installed_services):
            svc_data = dframe.services.add()
            #  Agent
            svc_data.agent.uid = svc_desc.agent.uid.bytes
            svc_data.agent.name = svc_desc.agent.name
            svc_data.agent.version = svc_desc.agent.version
            svc_data.agent.vendor.uid = svc_desc.agent.vendor_uid.bytes
            svc_data.agent.platform.uid = svc_desc.agent.platform_uid.bytes
            svc_data.agent.platform.version = svc_desc.agent.platform_version
            svc_data.agent.classification = svc_desc.agent.classification
            #  API
            for api in svc_desc.api:
                api_pb = svc_data.api.add()
                api_pb.uid = api.uid.bytes
                api_pb.name = api.name
                api_pb.revision = api.revision
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
        reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def on_running(self, session: TSession, msg: RequestMessage):
        """Handle REQUEST/RUNNING_SERVICES message.
"""
        log.debug("%s.on_running(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply data frames
        self.send(reply, session)
    def on_providers(self, session: TSession, msg: RequestMessage):
        """Handle REQUEST/INTERFACE_PROVIDERS message.
"""
        log.debug("%s.on_providers(%s)", self.__class__.__name__, session.routing_id)
        dframe = pb.RequestInterfaceProviders()
        dframe.ParseFromString(msg.data[0])
        interface_uid = dframe.interface_uid
        reply = self.protocol.create_reply_for(msg)
        # create reply data frames
        dframe = pb.ReplyInterfaceProviders()
        for svc_desc in (svc for svc in self.impl.installed_services):
            for api in svc_desc.api:
                if api.uid.bytes == interface_uid:
                    dframe.agent_uid.append(svc_desc.agent.uid.bytes)
        reply.data.append(dframe.SerializeToString())
        self.send(reply, session)
    def on_start(self, session: TSession, msg: RequestMessage):
        """Handle REQUEST/START_SERVICE message.
"""
        log.debug("%s.on_start(%s)", self.__class__.__name__, session.routing_id)
        # start the requested service
        svc: NodeService
        dframe = pb.RequestStartService()
        dframe.ParseFromString(msg.data[0])
        agent_uid = UUID(bytes=dframe.agent_uid)
        try:
            svc_desc = self.impl.get_service(agent_uid)
            if dframe.multiinstance and self.impl.is_running(agent_uid):
                raise SaturninError("Service %s is already running" % agent_uid)
            svc = self.impl.add_service(svc_desc, ExecutionMode(dframe.mode))
            timeout: int = START_TIMEOUT if dframe.timeout == 0 else dframe.timeout
            svc.start(dframe.endpoints, timeout)
        except SaturninError as exc:
            errmsg = self.protocol.create_error_for(msg, ErrorCode.INTERNAL_SERVICE_ERROR)
            errdesc = errmsg.add_error()
            errdesc.code = 1
            errdesc.description = str(exc)
            self.send(errmsg, session)
        except ValueError as exc:
            errmsg = self.protocol.create_error_for(msg, ErrorCode.INTERNAL_SERVICE_ERROR)
            errdesc = errmsg.add_error()
            errdesc.code = 1
            errdesc.description = str(exc)
            self.send(errmsg, session)
        except TimeoutError:
            errmsg = self.protocol.create_error_for(msg, ErrorCode.REQUEST_TIMEOUT)
            errdesc = errmsg.add_error()
            errdesc.code = 1
            errdesc.description = str(exc)
            self.send(errmsg, session)
        except Exception as exc:
            errmsg = self.protocol.create_error_for(msg, ErrorCode.INTERNAL_SERVICE_ERROR)
            errdesc = errmsg.add_error()
            errdesc.code = 1
            errdesc.description = str(exc)
            self.send(errmsg, session)
        else:
            # all ok, create reply
            reply = self.protocol.create_reply_for(msg)
            dframe = pb.ReplyStartService()
            dframe.peer_uid = svc.uid.bytes
            dframe.mode = svc.mode.value
            dframe.endpoints.extend(svc.endpoints)
            reply.data.append(dframe.SerializeToString())
            self.send(reply, session)
    def on_stop(self, session: TSession, msg: RequestMessage):
        """Handle REQUEST/STOP_SERVICE message.
"""
        log.debug("%s.on_stop(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply
        self.send(reply, session)
    def on_req_provider(self, session: TSession, msg: RequestMessage):
        """Handle REQUEST/REQUEST_PROVIDER message.
"""
        log.debug("%s.on_req_provider(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply
        self.send(reply, session)
    def on_shutdown(self, session: TSession, msg: RequestMessage):
        """Handle REQUEST/SHUTDOWN message.
"""
        log.debug("%s.on_shutdown(%s)", self.__class__.__name__, session.routing_id)
        reply = self.protocol.create_reply_for(msg)
        # create reply
        self.send(reply, session)

class SaturninNodeServiceImpl(SimpleServiceImpl):
    """Implementation of Saturnin NODE service."""
    def __init__(self, stop_event: Any):
        super().__init__(stop_event)
        self.agent = SERVICE_AGENT
        self.api = SERVICE_API
        self.installed_services: List[ServiceDescriptor] = []
        self.services: List[NodeService] = []
    def initialize(self, svc: BaseService):
        super().initialize(svc)
        self.msg_handler = SaturninNodeMessageHandler(self.svc_chn, self)
        # Load information about installed services.
        self.installed_services = [entry.load() for entry in
                                   iter_entry_points('saturnin.service')]
    def finalize(self, svc: TService) -> None:
        """Service finalization.
"""
        log.debug("%s.finalize", self.__class__.__name__)
        for svc in self.services:
            try:
                svc.stop()
            except:
                svc.terminate()
        super().finalize(svc)
    def get_service(self, agent_uid: UUID) -> ServiceDescriptor:
        """Returns descriptor for installed service.

Raises:
    :ValueError: If service is not installed.
"""
        for svc in  self.installed_services:
            if svc.agent.uid == agent_uid:
                return svc
        raise ValueError("Service %s not installed" % agent_uid)
    def add_service(self, svc_descriptor: ServiceDescriptor, mode: ExecutionMode) -> NodeService:
        """Create and return new NodeService instance."""
        svc = NodeService(svc_descriptor, mode)
        svc.remotes[NODE_INTERFACE_UID.bytes] = get_best_endpoint(self.endpoints,
                                                                  ExecutionMode.THREAD,
                                                                  svc.mode)

        self.services.append(svc)
        return svc
    def is_running(self, agent_uid: UUID) -> bool:
        """Returns True if service is running."""
        for svc in self.services:
            if svc.agent_uid == agent_uid:
                return True
        return False
