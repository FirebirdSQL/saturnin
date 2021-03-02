#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/base.py
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

"""Saturnin abstract base class for Components

"""

from __future__ import annotations
from abc import ABC, abstractmethod
from firebird.base.types import ZMQAddress
from firebird.base.config import Config, StrOption

class ComponentConfig(Config):
    """Base Component configuration."""
    def __init__(self, name: str):
        super().__init__(name)
        self.logging_id: StrOption = \
            StrOption('logging_id', "Logging ID for this component instance")

class Component(ABC):
    """Abstract base class for Saturnin Components.
    """
    @abstractmethod
    def initialize(self, config: ComponentConfig) -> None:
        """Verify configuration and assemble component structural parts.
        """
    @abstractmethod
    def warm_up(self, ctrl_addr: Optional[ZMQAddress]) -> None:
        """Must initialize the ChannelManager and connect component to control channel
        at provided address.
        """
    @abstractmethod
    def run(self) -> None:
        """Component execution (main loop).
        """
