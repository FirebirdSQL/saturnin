#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/service.py
# DESCRIPTION:    Base module for implementation of Firebird Butler Services
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

"""Saturnin base module for implementation of Firebird Butler Services
"""

from __future__ import annotations
from typing import cast
from abc import abstractmethod
from firebird.base.config import ListOption
from saturnin.base import ZMQAddress, RouterChannel, ComponentConfig
from saturnin.component.micro import MicroService
from saturnin.protocol.fbsp import FBSPService

SVC_CHN = 'service'

class ServiceConfig(ComponentConfig):
    """Base data provider/consumer microservice configuration.
    """
    def __init__(self, name: str):
        super().__init__(name)
        self.endpoints: ListOption = \
            ListOption('endpoints', ZMQAddress, "List of service endpoints", required=True)

class Service(MicroService):
    """
    """
    def initialize(self, config: ServiceConfig) -> None:
        """Verify configuration and assemble service structural parts.
        """
        super().initialize(config)
        # Set endpoints this service binds
        self.endpoints[SVC_CHN] = config.endpoints.value.copy()
        #: Service protocol
        service = FBSPService(service=self.descriptor, peer=self.peer)
        service.log_context = self.logging_id
        #: Channel for communication with service clients.
        self.svc_channel = self.mngr.create_channel(RouterChannel, SVC_CHN, service,
                                                    routing_id=self.peer.uid.hex.encode('ascii'),
                                                    sock_opts={'maxmsgsize': 52428800,
                                                               'rcvhwm': 500,
                                                               'sndhwm': 500,})
        self.register_api_handlers(service)
    @abstractmethod
    def register_api_handlers(self, service: FBSPService) -> None:
        """Called by `initialize()` for registration of service API handlers and FBSP
        service event handlers.
        """
    def start_activities(self) -> None:
        """Start normal service activities.

        Must raise an exception when start fails.
        """
        super().start_activities()
        self.svc_channel.set_wait_in(True)
    def stop_activities(self) -> None:
        """Stop service activities.
        """
        super().stop_activities()
        cast(FBSPService, self.svc_channel.protocol).close(self.svc_channel)
        self.svc_channel.set_wait_in(False)
