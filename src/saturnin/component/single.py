# SPDX-FileCopyrightText: 2023-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/single.py
# DESCRIPTION:    Single service controller and executor
# CREATED:        10.2.2023
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
# Copyright (c) 2023 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Simplified controller and executor for running a single Saturnin service.

This module provides `.SingleController` and `.SingleExecutor` classes to
streamline the process of configuring, starting, and managing a single
Saturnin service instance. It acts as a higher-level abstraction over
the more detailed `.DirectController` and `.ThreadController` implementations,
allowing for easier integration or standalone execution of services.
"""

from __future__ import annotations

import uuid
import warnings
from configparser import DEFAULTSECT, ConfigParser
from pathlib import Path
from typing import Self

import zmq
from saturnin.base import (
    SECTION_LOCAL_ADDRESS,
    SECTION_NET_ADDRESS,
    SECTION_NODE_ADDRESS,
    SECTION_PEER_UID,
    SECTION_SERVICE,
    SECTION_SERVICE_UID,
    ChannelManager,
    Error,
)

from firebird.base.config import EnvExtendedInterpolation
from firebird.base.logging import FStrMessage as _m
from firebird.base.logging import get_logger
from firebird.base.trace import TracedMixin

from .controller import DirectController, Outcome, ServiceExecConfig, ThreadController
from .registry import service_registry


class SingleController(TracedMixin):
    """A controller that manages a single service, allowing it to be executed
    either directly in the current thread (using `.DirectController`) or in a
    separate thread (using `.ThreadController`).

    This class simplifies the setup by managing the underlying controller type
    based on the `direct` flag.

    Arguments:
        parser: Optional `.ConfigParser` instance to be used for service
                configuration. If `None`, a new one is created.
        manager: Optional `.ChannelManager` to use. If `None`, a new one is
                 created and managed internally.
        direct: If `True`, the service will be run using an internal
                `.DirectController`. If `False` (default), a .`ThreadController`
                is used.
    """
    def __init__(self, *, parser: ConfigParser | None=None, manager: ChannelManager | None=None,
                 direct: bool=False):
        #: Use DirectController instead ThreadController
        self.direct: bool = direct
        #: Channel manager
        self.mngr: ChannelManager = manager
        self._ext_mngr: bool = manager is not None
        if manager is None:
            self.mngr = ChannelManager(zmq.Context.instance())
        #: ConfigParser with service configuration
        self.config: ConfigParser = \
            ConfigParser(interpolation=EnvExtendedInterpolation()) if parser is None else parser
        #: Service controller
        self.controller: ThreadController | DirectController = None
        #: Registry with ServiceDescriptors for services that could be run
        #
        self.config[SECTION_LOCAL_ADDRESS] = {}
        self.config[SECTION_NODE_ADDRESS] = {}
        self.config[SECTION_NET_ADDRESS] = {}
        self.config[SECTION_SERVICE_UID] = {}
        self.config[SECTION_PEER_UID] = {}
        # Defaults
        self.config[DEFAULTSECT]['here'] = str(Path.cwd())
        # Assign Agent IDs for available services
        self.config[SECTION_SERVICE_UID].update((sd.name, sd.uid.hex) for sd
                                                in service_registry)
        #
    def configure(self, *, section: str=SECTION_SERVICE) -> None:
        """Configures the service to be run.

        This method loads the service configuration from the `.config`
        (`.ConfigParser` instance), validates it, and instantiates the
        appropriate inner controller (`.DirectController` or `.ThreadController`)
        for the specified service.

        Arguments:
            section: Configuration section name in `.config` that contains
                     the service specification (e.g., its agent UID).
                     Defaults to `SECTION_SERVICE`.
        """
        svc_cfg: ServiceExecConfig = ServiceExecConfig(section)
        svc_cfg.load_config(self.config)
        svc_cfg.validate()
        peer_uid = uuid.uuid1()
        # Assign Peer ID to service section (instance)
        self.config[SECTION_PEER_UID][section] = peer_uid.hex
        #
        #
        controller_class = DirectController if self.direct else ThreadController
        if svc_cfg.agent.value in service_registry:
            self.controller = controller_class(service_registry[svc_cfg.agent.value],
                                               name=svc_cfg.name, peer_uid=peer_uid,
                                               manager=self.mngr)
        else:
            raise Error(f"Unknonw agent in section '{section}'")
    def start(self, *, timeout: int=10000) -> None:
        """Starts service.

        Arguments:
            timeout: Timeout for starting the service. `None` (infinity), or a floating
                     point number specifying a timeout for the operation in seconds (or
                     fractions thereof) [Default: 10s].

        Raises:
            ServiceError: On error in communication with service.
            TimeoutError: When service does not start in time.
        """
        try:
            self.controller.configure(self.config, self.controller.name)
            self.controller.start(timeout=timeout)
        except:
            self.stop()
            raise
    def stop(self, *, timeout: int=10000) -> None:
        """Stop runing service.

        Arguments:
            timeout: Timeout for stopping the service. `None` (infinity), or a floating
                     point number specifying a timeout for the operation in seconds (or
                     fractions thereof) [Default: 10s].

        Raises:
            ServiceError: On error in communication with service.
            TimeoutError: When service does not stop in time.
        """
        if not self.direct:
            try:
                self.controller.stop(timeout=timeout)
            except Exception as exc:
                get_logger(self).error(_m("Error while stopping the service: {args[0]}", args=exc.args))
                if self.controller.is_running():
                    warnings.warn(f"Stopping service {self.controller.name} failed, "
                                  f"service thread terminated", RuntimeWarning)
                    self.controller.terminate()
    def join(self, timeout=None) -> None:
        """Wait until service stops.

        Arguments:
            timeout: Floating point number specifying a timeout for the operation in
                     seconds (or fractions thereof).
        """
        self.controller.join(timeout)

class SingleExecutor:
    """A context manager for executing a single Saturnin service.

    This class simplifies the lifecycle management of a `SingleController`,
    ensuring proper initialization and cleanup (like ZMQ context termination)
    when used in a `with` statement.

    Arguments:
        direct: If `True`, the underlying `.SingleController` will be configured
                to run the service directly in the current thread. If `False`
                (default), the service runs in a separate thread.
    """
    def __init__(self, *, direct: bool = False):
        #: Use DirectController instead ThreadController
        self.direct: bool = direct
        #: Channel manager
        self.mngr: ChannelManager = None
        #: Controller
        self.controller: SingleController = None
    def __enter__(self) -> Self:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.mngr is not None:
            self.mngr.shutdown(forced=True)
        zmq.Context.instance().term()
    def configure(self, cfg_files: list[str], *, section: str=SECTION_SERVICE) -> None:
        """Initializes and configures the internal `SingleController`.

        This involves creating a `.ChannelManager`, instantiating a `.SingleController`
        with the specified `direct` mode, reading configuration files into the
        controller's `.ConfigParser`, and then calling the controller's `configure`
        method.

        Arguments:
          cfg_files: A list of paths to configuration files to be read.
          section:   The name of the configuration section that specifies the
                     service to be run. Defaults to `SECTION_SERVICE`.
        """
        self.mngr = ChannelManager(zmq.Context.instance())
        self.controller: SingleController = SingleController(manager=self.mngr,
                                                             direct=self.direct)
        self.controller.config.read(cfg_files)
        self.controller.configure(section=section)
    def run(self) -> tuple[Outcome, list[str]] | None:
        """Runs the configured service.

        If the executor is configured for non-direct (threaded) execution, this
        method starts the service, waits for it to join (handling KeyboardInterrupt
        for graceful shutdown), and then returns the execution outcome.

        If configured for direct execution, this method starts the service, which
        will block until it finishes or is interrupted. In direct mode, this
        method returns `None` as the outcome is managed within the blocking call.

        Returns:
            tuple[Outcome, list[str]] | None:
                - If not in `direct` mode: A tuple containing the service's
                  execution `Outcome` and a list of strings with details (e.g., error messages).
                - If in `direct` mode: `None`.
        """
        self.controller.start()
        result = None
        if not self.direct:
            try:
                self.controller.join()
                raise KeyboardInterrupt() # This, or direct call to executor.stop()
            except KeyboardInterrupt: # SIGINT
                self.controller.stop()
            finally:
                result = (self.controller.controller.outcome, self.controller.controller.details)
        return result
