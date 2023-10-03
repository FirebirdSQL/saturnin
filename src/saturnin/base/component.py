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
from typing import Optional
from uuid import UUID
from abc import ABC, abstractmethod
from firebird.base.types import ZMQAddress
from firebird.base.config import Config, StrOption, UUIDOption

def create_config(_cls: Type[ComponentConfig], agent: UUID, name: str) -> ComponentConfig: # pragma: no cover
    """Returns newly created `ComponentConfig` instance.

    Intended to be used with `functools.partial` in `.ServiceDescriptor.config` definitions.

    Arguments:
      _cls:  Class for component configuration.
      agent: Component identification.
      name:  Name to be used by configuration class.
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
            UUIDOption('agent', "Agent identification. Do NOT change!")
        #: Logging ID for this component instance
        self.logging_id: StrOption = \
            StrOption('logging_id', "Logging ID for this component instance")

class Component(ABC):
    """Abstract base class for Saturnin Components.
    """
    @abstractmethod
    def initialize(self, config: ComponentConfig) -> None:
        """Verify configuration and assemble component structural parts.

        Arguments:
           config: Component configuration.
        """
    @abstractmethod
    def warm_up(self, ctrl_addr: Optional[ZMQAddress]) -> None:
        """Must initialize the `.ChannelManager` and connect component to control channel
        at provided address.

        Arguments:
            ctrl_addr: Controller's address for ICCP communication with component.
        """
    @abstractmethod
    def run(self) -> None:
        """Component execution (main loop).
        """
