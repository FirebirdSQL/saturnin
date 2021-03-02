#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/micro.py
# DESCRIPTION:    Base module for implementation of Firebird Butler Microservices
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

"""Saturnin base module for implementation of Firebird Butler Microservices
"""

from __future__ import annotations
from typing import Union, Dict, List, cast
import sys
import os
import platform
import threading
import uuid
import zmq
from weakref import proxy
from time import monotonic_ns
from heapq import heappush, heappop
from firebird.base.types import Conjunctive
from firebird.base.trace import TracedMixin
from saturnin.base import ZMQAddress, Component, PeerDescriptor, ServiceDescriptor, \
     ServiceError, Direction, State, Outcome, ChannelManager, Channel, PairChannel, \
     ComponentConfig, ConfigProto, PrioritizedItem
from saturnin.protocol.iccp import ICCPComponent

#: Service control channel name
SVC_CTRL = sys.intern('iccp')

class MicroService(Component, TracedMixin, metaclass=Conjunctive):
    """Saturnin Component for Firebird Burler Microservices.
    """
    def __init__(self, zmq_context: zmq.Context, descriptor: ServiceDescriptor, *,
                 peer_uid: uuid.UUID=None):
        """
        Arguments:
            zmq_context: ZeroMQ Context.
            descriptor: Service descriptor.
            peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
        """
        self._heap: List = []
        #: Service execution outcome
        self.outcome: Outcome = Outcome.UNKNOWN
        #: Service execution outcome details
        self.details: Union[Exception, List[str]] = None
        #: Service internal state
        self.state: State = State.UNKNOWN_STATE
        #: Event to stop the component
        self.stop: threading.Event = threading.Event()
        #: ChannelManager instance.
        self.mngr: ChannelManager = ChannelManager(zmq_context)
        self.mngr.log_context = proxy(self)
        #: Dictionary with endpoints to which the component binds.
        #: Key is channel name, value is list of ZMQAddress instances.
        #: Initially empty.
        self.endpoints: Dict[str, List[ZMQAddress]] = {}
        #: Service desriptor.
        self.descriptor: ServiceDescriptor = descriptor
        #: Peer descriptor for this component.
        self.peer: PeerDescriptor = PeerDescriptor(uuid.uuid1() if peer_uid is None else peer_uid,
                                                   os.getpid(), platform.node())
    def __str__(self):
        return self.logging_id
    __repr__ = __str__
    def handle_stop_component(self, exc: Exception=None) -> None:
        """ICCP event handler. Called when commponent should stop its operation.
        It stops the component by setting the `~Component.stop` event.

        Arguments:
           exc: Exception that describes the reason why component should stop. If not
                provided, the component should stop on controller's request.
        """
        if exc is not None:
            self.outcome = Outcome.ERROR
            self.details = exc
        self.stop.set()
    def handle_config_request(self, config: ConfigProto) -> None:
        """ICCP event handler. Called when controller requested reconfiguration.

        Must raise an exception if configuration fails for any reason.

        By default, the component does not support run-time configuration, so it raises
        NotImplementedError.

        Arguments:
           config: New configuration provided by controller.
        """
        raise NotImplementedError("Service does not support run-time configuration")
    def schedule(self, action: Callable, after: int) -> None:
        """Schedule action to be executed after specified time.

        Action is executed in `run()` main I/O loop not sooner than after specified number
        of milliseconds from time when `schedule()` is called. However, the actual delay
        could be longer than specified (depends on time spent in message handlers and other
        factors).

        Arguments:
            action: Callable (without arguments) to be executed. Use `functools.partial`
                    if callable requires arguments.
            after:  Delay in milliseconds.
        """
        heappush(self._heap, PrioritizedItem(monotonic_ns() + (after * 1000000), action))
    def get_timeout(self) -> int:
        """Returns timeout to next scheduled action.
        """
        if not self._heap:
            return None
        back = []
        i = len(self._heap)
        now = monotonic_ns()
        while self._heap and (item := heappop(self._heap)).priority < now:
            back.append(item)
        if len(back) != i:
            heappush(self._heap, item)
        for b in back:
            heappush(self._heap, b)
        return max(int((item.priority - now) / 1000000), 0)
    def run_scheduled(self) -> None:
        """Run scheduled actions.
        """
        while self._heap:
            item = heappop(self._heap)
            if item.priority < monotonic_ns():
                item.item()
            else:
                heappush(self._heap, item)
                break
    def initialize(self, config: ComponentConfig) -> None:
        """Verify configuration and assemble component structural parts.
        """
        config.validate() # Fail early!
        if config.logging_id.value is not None:
            self._logging_id_ = config.logging_id.value
    def bind_endpoints(self) -> None:
        """Bind endpoints used by component.
        """
        for name, addr_list in self.endpoints.items():
            chn: Channel = self.mngr.channels.get(name)
            for i in range(len(addr_list)):
                self.endpoints[name][i] = chn.bind(addr_list[i])
    def aquire_resources(self) -> None:
        """Aquire resources required by component (open files, connect to other services etc.).

        Must raise an exception when resource aquisition fails.
        """
    def release_resources(self) -> None:
        """Release resources aquired by component (close files, disconnect from other services etc.)
        """
    def start_activities(self) -> None:
        """Start normal component activities.

        Must raise an exception when start fails.
        """
    def stop_activities(self) -> None:
        """Stop component activities.
        """
    def warm_up(self, ctrl_addr: Optional[ZMQAddress]) -> None:
        """Initializes the ChannelManager and connects component to control channel.
        """
        if ctrl_addr is not None:
            # Service control channel
            iccp = ICCPComponent(with_traceback=__debug__)
            iccp.on_stop_component = self.handle_stop_component
            iccp.on_config_request = self.handle_config_request
            chn: PairChannel = self.mngr.create_channel(PairChannel, SVC_CTRL, iccp,
                                                        wait_for=Direction.IN,
                                                        sock_opts={'rcvhwm': 5,
                                                                   'sndhwm': 5,})
            chn.protocol.log_context = self.logging_id
        self.mngr.warm_up()
        if ctrl_addr is not None:
            chn.connect(ctrl_addr)
            if not chn.can_send():
                raise ServiceError("Broken component control channel")
        try:
            self.bind_endpoints()
            self.aquire_resources()
            self.start_activities()
        except Exception as exc:
            if ctrl_addr is not None:
                chn.send(cast(ICCPComponent, chn.protocol).error_msg(exc), chn.session)
            self.mngr.shutdown()
            raise
        else:
            if ctrl_addr is not None:
                chn.send(cast(ICCPComponent, chn.protocol).ready_msg(self.peer, self.endpoints),
                         chn.session)
            self.state = State.READY
    def run(self) -> None:
        """Component execution (main loop).
        """
        self.state = State.RUNNING
        ctrl_chn: PairChannel = self.mngr.channels.get(SVC_CTRL)
        try:
            while not self.stop.is_set():
                events = self.mngr.wait(self.get_timeout())
                if events:
                    # Messages from service control channel have top priority
                    if ctrl_chn in events:
                        ctrl_chn.receive()
                        if self.stop.is_set():
                            continue # stop quickly
                    # Channels waiting for output have precedence
                    if self.mngr.has_pollout():
                        for chn, event in events.items():
                            if Direction.OUT in event:
                                chn.on_output_ready(chn)
                    # Now process incomming messages
                    for chn, event in events.items():
                        if Direction.IN in event:
                            chn.receive()
                # Now it's time for scheduled actions
                self.run_scheduled()
            # Gracefully stop the service
            self.state = State.STOPPED
            self.stop_activities()
            self.release_resources()
            if self.outcome is Outcome.UNKNOWN:
                self.outcome = Outcome.OK
            ctrl_chn.send(cast(ICCPComponent, ctrl_chn.protocol).finished_msg(self.outcome,
                                                                              self.details),
                          ctrl_chn.session)
            self.mngr.shutdown()
            self.state = State.FINISHED
        except Exception as exc:
            self.state = State.ABORTED
            try:
                # try send report to controller
                ctrl_chn.send(cast(ICCPComponent, ctrl_chn.protocol).error_msg(exc),
                              ctrl_chn.session)
            except:
                pass
            try:
                self.mngr.shutdown(forced=True)
            except:
                pass
    @property
    def logging_id(self) -> str:
        "Returns _logging_id_ or <agent_name>[<peer.uid.hex>]"
        return getattr(self, '_logging_id_', f'{self.descriptor.agent.name}[{self.peer.uid.hex}]')

