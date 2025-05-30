# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
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

"""Saturnin base module for implementation of Firebird Butler Microservices.

This module provides the `MicroService` base class, which handles common
microservice lifecycle management, communication with a controller via ICCP,
and a basic event loop for handling ZMQ messages and scheduled tasks.
"""

from __future__ import annotations

import os
import platform
import threading
import uuid
from collections.abc import Callable
from contextlib import suppress
from heapq import heappop, heappush
from time import monotonic_ns
from typing import Final, cast
from weakref import proxy

import zmq
from saturnin.base import (
    Channel,
    ChannelManager,
    Component,
    ComponentConfig,
    ConfigProto,
    Direction,
    Outcome,
    PairChannel,
    PeerDescriptor,
    PrioritizedItem,
    ServiceDescriptor,
    ServiceError,
    State,
    ZMQAddress,
)
from saturnin.protocol.iccp import ICCPComponent

from firebird.base.trace import TracedMixin
from firebird.base.types import conjunctive

#: Service control channel name
SVC_CTRL: Final[str] = 'iccp'

class MicroService(Component, TracedMixin, metaclass=conjunctive):
    """Saturnin Component for Firebird Butler Microservices.

    Arguments:
        zmq_context: ZeroMQ Context.
        descriptor: Service descriptor.
        peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
    """
    def __init__(self, zmq_context: zmq.Context, descriptor: ServiceDescriptor, *,
                 peer_uid: uuid.UUID | None=None):
        self._heap: list = []
        #: Service execution outcome
        self.outcome: Outcome = Outcome.UNKNOWN
        #: Service execution outcome details
        self.details: Exception | list[str] = None
        #: Service internal state
        self.state: State = State.UNKNOWN_STATE
        #: Event to stop the component
        self.stop: threading.Event = threading.Event()
        #: ChannelManager instance.
        self.mngr: ChannelManager = ChannelManager(zmq_context)
        #: Dictionary with endpoints to which the component binds.
        #: Key is channel name, value is list of ZMQAddress instances.
        #: Initially empty.
        self.endpoints: dict[str, list[ZMQAddress]] = {}
        #: Service desriptor.
        self.descriptor: ServiceDescriptor = descriptor
        #: Peer descriptor for this component.
        self.peer: PeerDescriptor = PeerDescriptor(uuid.uuid1() if peer_uid is None else peer_uid,
                                                   os.getpid(), platform.node())
    def handle_stop_component(self, exc: Exception | None=None) -> None:
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
        `NotImplementedError`.

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
        """Returns the timeout in milliseconds until the next scheduled action.
        If no actions are scheduled, it returns 1000ms (1 second) as a default polling
        interval.
        """
        if not self._heap:
            return 1000
        back = []
        i = len(self._heap)
        now = monotonic_ns()
        while self._heap and (item := heappop(self._heap)).priority < now:
            back.append(item)
        if len(back) != i:
            heappush(self._heap, item)
        for value in back:
            heappush(self._heap, value)
        return max(int((item.priority - now) / 1000000), 0)
    def run_scheduled(self) -> None:
        """Executes any scheduled actions whose execution time (priority) is at or before
        the current monotonic time.
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

        Arguments:
            config: Service configuration.
        """
        config.validate() # Fail early!
        if config.logging_id.value is not None:
            self._agent_name_ = config.logging_id.value
    def bind_endpoints(self) -> None:
        """Binds all ZMQ endpoints defined in `.endpoints` using the respective channels
        from `.mngr`.
        """
        for name, addr_list in self.endpoints.items():
            chn: Channel = self.mngr.channels.get(name)
            for i, addr in enumerate(addr_list):
                #self.endpoints[name][i] = chn.bind(addr)
                addr_list[i] = chn.bind(addr)
    def aquire_resources(self) -> None:
        """Acquire resources required by component (e.g., open files, connect to other services).

        This method is called during the warm-up phase after basic initialization.
        Implementations should raise an exception if resource acquisition fails.
        """
    def release_resources(self) -> None:
        """Release resources acquired by the component (e.g., close files, disconnect from other services).

        This method is called during the graceful shutdown phase.
        """
    def start_activities(self) -> None:
        """Start normal component activities.

        Must raise an exception when start fails.
        """
    def stop_activities(self) -> None:
        """Stop component activities.
        """
    def warm_up(self, ctrl_addr: ZMQAddress | None) -> None:
        """Performs the warm-up sequence for the microservice.

        This includes:

        - Setting up the ICCP control channel if `ctrl_addr` is provided.
        - Warming up the `.ChannelManager` to create ZMQ sockets.
        - Connecting to the controller via ICCP.
        - Binding all service-defined endpoints via `.bind_endpoints()`.
        - Acquiring necessary resources via `aquire_resources()`.
        - Starting normal component activities via `.start_activities()`.
        - Sending a `READY` message to the controller upon success, or an `ERROR`
          message if any warm-up step fails.

        Arguments:
            ctrl_addr: The ZMQ address of the controller's control channel. If `None`,
                       the component runs without ICCP communication (e.g., standalone).
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
        """The main execution loop for the microservice.

        This loop continuously waits for I/O events on managed channels and
        processes them in a prioritized order:

        1. Messages on the ICCP control channel (if connected).
        2. Output-ready events on other channels.
        3. Input-ready events on other channels.

        After processing I/O, it executes any due scheduled actions via `.run_scheduled()`.

        The loop terminates when `.stop` event is set. Upon termination,
        it performs a graceful shutdown sequence: `.stop_activities()`,
        `.release_resources()`, sends a `FINISHED` (or `ERROR`) message to the
        controller, and shuts down the `.ChannelManager`.
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
            with suppress(Exception):
                # try send report to controller
                ctrl_chn.send(cast(ICCPComponent, ctrl_chn.protocol).error_msg(exc),
                              ctrl_chn.session)
            with suppress(Exception):
                self.mngr.shutdown(forced=True)
