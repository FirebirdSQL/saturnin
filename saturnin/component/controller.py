#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/controler.py
# DESCRIPTION:    Service controllers
# CREATED:        22.4.2019
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

"""Saturnin service controllers
"""

from __future__ import annotations
from typing import Dict, List, cast
import sys
import uuid
import zmq
import signal
import warnings
import ctypes
import weakref
from time import monotonic
from threading import Thread
from configparser import ConfigParser
from firebird.base.config import UUIDOption
from firebird.base.trace import TracedMixin
from saturnin.base import ZMQAddress, load, Error, ServiceError, PeerDescriptor, Outcome, \
     ServiceDescriptor, Direction, ChannelManager, PairChannel, INVALID, Component, Config
from saturnin.protocol.iccp import ICCPComponent, ICCPController, ICCPMessage, MsgType

#: Service control channel name
SVC_CTRL = sys.intern('iccp')

class ServiceExecConfig(Config):
    """Service executor configuration.
    """
    def __init__(self, name: str):
        super().__init__(name)
        self.agent: UUIDOption = UUIDOption('agent', "Agent UID", required=True)

class ServiceController(TracedMixin):
    """
    """
    def __init__(self, service: ServiceDescriptor, *, name: str=None,
                 peer_uid: uuid.UUID=None, manager: ChannelManager=None):
        """
        Arguments:
            service: Service to start.
            name:  Container name.
            peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
            manager: ChannelManager to be used.
        """
        self.outcome: Outcome = Outcome.UNKNOWN
        self.details: List[str] = []
        self.log_context = None
        self.name: str = service.agent.name if name is None else name
        self.peer_uid: uuid.UUID = peer_uid
        self.service: ServiceDescriptor = service
        self.peer: PeerDescriptor = None
        self.endpoints: Dict[str, List[ZMQAddress]] = {}
        self.config: Config = service.config()
        self.ctrl_addr: ZMQAddress = ZMQAddress(f'inproc://{uuid.uuid1().hex}')
        self.mngr: ChannelManager = manager
        self._ext_mngr: bool = manager is not None
    def __str__(self):
        return self.logging_id
    def configure(self, config: ConfigParser, section: str=None) -> None:
        """Loads and validates service configuration.

        Arguments:
            config: ConfigParser instance with service configuration.
            section: Name of section with service configuration. If not present, uses
                     `ServiceContainer.name` value.
        """
        self.config.load_config(config, self.name if section is None else section)
        self.config.validate()
    @property
    def logging_id(self) -> str:
        "Returns qualified class name and agent name."
        return f'{self.__class__.__qualname__}[{self.service.agent.name}]'

class DirectController(ServiceController):
    """Service controller that starts the service in current thread.

    Although ICCP is used to start/stop the service, it's not possible to perform any ICCP
    interactions with the service while it's running.

    Important:
        The service could be stopped only via automatically installed SIGINT handler.
    """
    def stop_signal_handler(self, signum: int, param) -> None:
        """The `signal.signal()` SIGINT handler that sends ICCP STOP message to the service.
        """
        chn: PairChannel = self.mngr.channels[SVC_CTRL]
        chn.send(cast(ICCPController, chn.protocol).stop_msg(), chn.session)
    def handle_stop_controller(self, exc: Exception) -> None:
        """Called when controller should stop its operation due to error condition.

        Arguments:
           exc: Exception that describes the reason why component should stop.
        """
        raise ServiceError("Internal controller error") from exc
    def start(self, *, timeout: int=10000) -> None:
        """Start the service.

        Arguments:
            timeout: Only for compatibility with ThreadController. The value is ignored.

        Important:
            Will not return until service is stopped via SIGINT, or exception is raised.

        Raises:
            ServiceError: On error in communication with service.
        """
        if not self._ext_mngr:
            self.mngr = ChannelManager(zmq.Context.instance())
            self.mngr.log_context = weakref.proxy(self)
        iccp = ICCPController()
        iccp.on_stop_controller = self.handle_stop_controller
        chn: PairChannel = self.mngr.create_channel(PairChannel, SVC_CTRL, iccp,
                                                    wait_for=Direction.IN,
                                                    sock_opts={'rcvhwm': 5, 'sndhwm': 5,})
        chn.protocol.log_context = self.log_context
        #
        factory = load(self.service.factory)
        svc: Component = factory(zmq.Context.instance(), self.service)
        svc.initialize(self.config)
        # 1st phase successful
        self.mngr.warm_up()
        chn.bind(self.ctrl_addr)
        try:
            # 2nd phase
            svc.warm_up(self.ctrl_addr) # Creates sockets, connects to `iccp`
            result = chn.wait(1000)
            if result == Direction.IN:
                msg: ICCPMessage = chn.receive()
                if msg is INVALID:
                    raise ServiceError("Invalid response from service")
                elif msg.msg_type is MsgType.READY:
                    self.peer = msg.peer.copy()
                    self.endpoints = msg.endpoints.copy()
                elif msg.msg_type is MsgType.ERROR:
                    raise ServiceError(msg.error)
                else:
                    raise ServiceError("ICCP protocol error - unexpected message")
            else:
                raise ServiceError("Service did not started in time")
            # All green to run the service
            old = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self.stop_signal_handler)
            try:
                svc.run()
                result = chn.wait(100)
                if result == Direction.IN:
                    msg: ICCPMessage = chn.receive()
                    if msg is INVALID:
                        raise ServiceError("Invalid response from service")
                    elif msg.msg_type is MsgType.ERROR:
                        raise ServiceError(msg.error)
                else:
                    warnings.warn("Service shutdown not confirmed", RuntimeWarning)
            finally:
                signal.signal(signal.SIGINT, old)
        finally:
            if not self._ext_mngr:
                self.mngr.shutdown(forced=True)

def service_thread(service: ServiceDescriptor, config: Config, ctrl_addr: ZMQAddress,
                   peer_uid: uuid.UUID=None):
    """Thread target code to run the service.

    Arguments:
        svc_descriptor: Service descriptor.
        config:         Service configuration.
        ctrl_addr:      Address for control ZMQ socket.
        peer_uid:       Peer ID.
    """
    try:
        ctx = zmq.Context.instance()
        pipe = ctx.socket(zmq.DEALER)
        pipe.CONNECT_TIMEOUT = 5000 # 5sec
        pipe.IMMEDIATE = 1
        pipe.LINGER = 5000 # 5sec
        pipe.SNDTIMEO = 5000 # 5sec
        try:
            factory = load(service.factory)
            svc: Component = factory(zmq.Context.instance(), service, peer_uid=peer_uid)
            svc.initialize(config)
        except Exception as exc:
            pipe.connect(ctrl_addr)
            iccp = ICCPComponent()
            pipe.send_multipart(iccp.error_msg(exc).as_zmsg())
            raise
        finally:
            pipe.close(100)
        svc.warm_up(ctrl_addr) # Creates sockets, connects to `iccp`
        svc.run()
    except:
        pass

class ThreadController(ServiceController):
    """Service controller that starts the service in separate thread.
    """
    def __init__(self, service: ServiceDescriptor, *, name: str=None,
                 peer_uid: uuid.UUID=None, manager: ChannelManager=None):
        """
        Arguments:
            service: Service to start.
            name:  Container name.
            peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
        """
        super().__init__(service, name=name, peer_uid=peer_uid, manager=manager)
        self.runtime: Thread = None
    def handle_stop_controller(self, exc: Exception) -> None:
        """Called when controller should stop its operation due to error condition.

        Arguments:
           exc: Exception that describes the reason why component should stop.
        """
        raise ServiceError("Internal controller error") from exc
    def is_running(self) -> bool:
        """Returns True if service is running.
        """
        if self.runtime is None:
            return False
        if self.runtime.is_alive():
            return True
        # It's dead, so dispose the runtime
        self.runtime = None
        return False
    def start(self, *, timeout: int=10000) -> None:
        """Start the service.

        Arguments:
            timeout: Timeout (in milliseconds) to wait for service to report it's ready.

        Raises:
            ServiceError: On error in communication with service.
            TimeoutError: When timeout expires.
        """
        if not self._ext_mngr:
            self.mngr = ChannelManager(zmq.Context.instance())
            self.mngr.log_context = weakref.proxy(self)
        iccp = ICCPController()
        iccp.on_stop_controller = self.handle_stop_controller
        chn: PairChannel = self.mngr.create_channel(PairChannel, f'{self.name}.{SVC_CTRL}',
                                                    iccp, wait_for=Direction.IN,
                                                    sock_opts={'rcvhwm': 5, 'sndhwm': 5,})
        chn.protocol.log_context = self.log_context
        self.mngr.warm_up()
        chn.bind(self.ctrl_addr)
        #
        self.runtime = Thread(target=service_thread, name=self.name,
                              args=(self.service, self.config, self.ctrl_addr, self.peer_uid),
                              daemon=False)
        self.runtime.start()
        #
        try:
            result = chn.wait(timeout)
            if result == Direction.IN:
                msg: ICCPMessage = chn.receive()
                if msg is INVALID:
                    raise ServiceError("Invalid response from service")
                elif msg.msg_type is MsgType.READY:
                    self.peer = msg.peer.copy()
                    self.endpoints = msg.endpoints.copy()
                elif msg.msg_type is MsgType.ERROR:
                    raise ServiceError(msg.error)
                else:
                    raise ServiceError("ICCP protocol error - unexpected message")
            elif not self.is_running():
                raise ServiceError("Service start failed for unknown reason")
            else:
                raise TimeoutError("Service did not started in time")
        except Exception:
            if not self._ext_mngr:
                self.mngr.shutdown(forced=True)
            raise
    def stop(self, *, timeout: int=10000) -> None:
        """Stop the service. Does nothing if service is not running.

        Arguments:
            timeout: None (infinity), or timeout (in milliseconds) for the operation.

        Raises:
            ServiceError: On error in communication with service.
            TimeoutError: When service does not stop in time.
        """
        s = monotonic()
        try:
            chn: PairChannel = self.mngr.channels[f'{self.name}.{SVC_CTRL}']
            if self.is_running():
                chn.send(cast(ICCPController, chn.protocol).stop_msg(), chn.session)
                result = chn.wait(timeout)
                if result == Direction.IN:
                    msg: ICCPMessage = chn.receive()
                    if msg is INVALID:
                        self.outcome = Outcome.ERROR
                        self.details = ["Invalid response from service"]
                        raise ServiceError("Invalid response from service")
                    elif msg.msg_type is MsgType.ERROR:
                        self.outcome = Outcome.ERROR
                        self.details = [msg.error]
                        raise ServiceError(msg.error)
                    elif msg.msg_type is MsgType.FINISHED:
                        self.outcome = msg.outcome
                        self.details = msg.details
                else:
                    warnings.warn("Service shutdown not confirmed", RuntimeWarning)
                #
                if self.is_running():
                    e = monotonic()
                    if timeout is not None:
                        timeout = timeout - int((e-s) * 1000)
                        if timeout < 0:
                            timeout = 0
                    self.runtime.join(timeout)
                    if self.runtime.is_alive():
                        raise TimeoutError("The service did not stop in time")
            else:
                result = chn.wait(0)
                if result == Direction.IN:
                    msg: ICCPMessage = chn.receive()
                    if msg is INVALID:
                        self.outcome = Outcome.ERROR
                        self.details = ["Invalid response from service"]
                        raise ServiceError("Invalid response from service")
                    elif msg.msg_type is MsgType.ERROR:
                        self.outcome = Outcome.ERROR
                        self.details = [msg.error]
                        raise ServiceError(msg.error)
                    elif msg.msg_type is MsgType.FINISHED:
                        self.outcome = msg.outcome
                        self.details = msg.details
        finally:
            if not self._ext_mngr:
                self.mngr.shutdown(forced=True)
    def terminate(self) -> None:
        """Terminate the service.

        Terminate should be called ONLY when call to stop() (with sensible timeout) fails.
        Does nothing when service is not running.

        Raises:
            Error:  When service termination fails.
        """
        if self.is_running():
            tid = ctypes.c_long(self.runtime.ident)
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(SystemExit))
            if res == 0:
                raise Error("Service termination failed due to invalid thread ID.")
            if res != 1:
                # if it returns a number greater than one, you're in trouble,
                # and you should call it again with exc=NULL to revert the effect
                ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
                raise Error("Service termination failed due to PyThreadState_SetAsyncExc failure")
    def join(self, timeout=None) -> None:
        """Wait until service stops.

        Arguments:
            timeout: Floating point number specifying a timeout for the operation in
                     seconds (or fractions thereof).
        """
        if self.runtime:
            self.runtime.join(timeout)
