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
# pylint: disable=R0903

"""Single service controller and executor.


"""

from __future__ import annotations
from typing import List, Union, Tuple, Any
import uuid
import weakref
import warnings
from pathlib import Path
from configparser import ConfigParser, ExtendedInterpolation, DEFAULTSECT
import zmq
from firebird.base.logging import LoggingIdMixin, get_logger
from firebird.base.trace import TracedMixin
from saturnin.base import (Error, ChannelManager, SECTION_LOCAL_ADDRESS,
                           SECTION_NET_ADDRESS, SECTION_NODE_ADDRESS, SECTION_PEER_UID,
                           SECTION_SERVICE_UID, SECTION_SERVICE)
from .controller import ThreadController, DirectController, ServiceExecConfig, Outcome
from .registry import service_registry

class SingleController(LoggingIdMixin, TracedMixin):
    """Service controller that manages service executed directly or in separate thread.
    """
    def __init__(self, *, parser: ConfigParser=None, manager: ChannelManager=None,
                 direct: bool=False):
        """
        Arguments:
            controller_class: Inner controller class.
            parser: ConfigParser instance to be used for service configuration.
            manager: ChannelManager to be used.
            direct: Use DirectController or ThreadController.
        """
        #: Use DirectController instead ThreadController
        self.direct: bool = direct
        self.log_context = None
        #: Channel manager
        self.mngr: ChannelManager = manager
        self._ext_mngr: bool = manager is not None
        if manager is None:
            self.mngr = ChannelManager(zmq.Context.instance())
            self.mngr.log_context = weakref.proxy(self)
        #: ConfigParser with service configuration
        self.config: ConfigParser = \
            ConfigParser(interpolation=ExtendedInterpolation()) if parser is None else parser
        #: Service controller
        self.controller: Union[ThreadController, DirectController] = None
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
        """
        Arguments:
            section: Configuration section with service specification.
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
            self.controller.log_context = self.log_context
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
            except Exception as exc: # pylint: disable=W0703
                get_logger(self).error("Error while stopping the service: {args[0]}", exc)
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

class SingleExecutor():
    """Single service executor context manager.
    """
    def __init__(self, log_context: Any, *, direct: bool = False):
        """
        Arguments:
            log_context: Log context for this executor.
            direct: Use `.DirectController` (True) or `.ThreadController`.
        """
        #: Use DirectController instead ThreadController
        self.direct: bool = direct
        self.log_context = log_context
        #: Channel manager
        self.mngr: ChannelManager = None
        #: Controller
        self.controller: SingleController = None
    def __enter__(self) -> SingleExecutor:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.mngr is not None:
            self.mngr.shutdown(forced=True)
        zmq.Context.instance().term()
    def configure(self, cfg_files: List[str], *, section: str=SECTION_SERVICE) -> None:
        """Executor configuration.

        Arguments:
          cfg_files: List of configuration files.
          section:   Configuration section name with service specification.
        """
        self.mngr = ChannelManager(zmq.Context.instance())
        self.mngr.log_context = self.log_context
        self.controller: SingleController = SingleController(manager=self.mngr,
                                                             direct=self.direct)
        self.controller.log_context = self.log_context
        self.controller.config.read(cfg_files)
        self.controller.configure(section=section)
    def run(self) -> List[Tuple[str, Outcome, List[str]]]:
        """Runs the service in main or separate thread.

        Returns:
          Tuple with (service_name, outcome, details).

        outcome: `.Outcome` of service execution.
        details: List of strings with additional outcome information (typically error text)
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
