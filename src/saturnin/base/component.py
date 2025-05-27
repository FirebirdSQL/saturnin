# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/base/component.py
# DESCRIPTION:    Abstract base class for Saturnin Components
# CREATED:        3.12.2020
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Saturnin abstract base class for Components.

Saturnin components are microservices, services or other software components that could be
executed on Saturnin platform, typically under supervision of Controller(s).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from firebird.base.config import Config, StrOption, UUIDOption
from firebird.base.types import ZMQAddress


def create_config(_cls: type[ComponentConfig], agent: UUID, name: str) -> ComponentConfig:
    """Returns a newly created `ComponentConfig` instance (or a subclass instance).

    This function is primarily intended to be used with `functools.partial`
    when defining the `config` factory in `ServiceDescriptor` instances.

    Arguments:
        _cls: The `ComponentConfig` class (or a subclass of it) to instantiate.
        agent: The UUID for component identification, to be set in the config.
        name: The name to be used by the configuration class (often for section naming).

    Returns:
        An initialized instance of the provided `_cls`.
    """
    result: ComponentConfig = _cls(name)
    result.agent.value = agent
    return result

class ComponentConfig(Config):
    """Base Component configuration.

    Arguments:
       name: Component name (used as conf. file section name for component).
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Agent identification
        self.agent: UUIDOption = \
            UUIDOption('agent', "Unique agent identification. Do NOT change!")
        #: Logging ID for this component instance
        self.logging_id: StrOption = \
            StrOption('logging_id', "Logging ID (custom agent name) for this component instance (set in agent's `_agent_name_` attribute)")

class Component(ABC):
    """Abstract base class for Saturnin Components, which represent executable units like
    microservices or services managed by the platform.
    """
    @abstractmethod
    def initialize(self, config: ComponentConfig) -> None:
        """Verify configuration and assemble component structural parts.

        Arguments:
           config: Component configuration.
        """
    @abstractmethod
    def warm_up(self, ctrl_addr: ZMQAddress | None) -> None:
        """Initializes essential communication infrastructure for the component.

    Implementations must initialize their `ChannelManager` and establish a
    connection to the control channel at the provided `ctrl_addr`. This
    connection is typically used for Inter-Component Communication Protocol (ICCP)
    with a controller.

    Arguments:
        ctrl_addr: The ZMQ address of the controller's control channel.
                   If `None`, the component might operate in a standalone mode
                   or a specific behavior should be defined by the implementer.
    """
    @abstractmethod
    def run(self) -> None:
        """Component execution (main loop).
        """
