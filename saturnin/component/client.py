#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/component/client.py
# DESCRIPTION:    Base module for implementation of Firebird Butler Service clients
# CREATED:        15.1.2021
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

"""Saturnin base module for implementation of Firebird Butler Service clients


"""

from __future__ import annotations
import os
import platform
from struct import pack
from uuid import UUID
from saturnin.base import Error, ZMQAddress, Channel, TIMEOUT, INVALID, AgentDescriptor, \
     PeerDescriptor
from saturnin.protocol.fbsp import FBSPClient, FBSPSession, FBSPMessage, \
     WelcomeMessage, ErrorMessage, MsgType

class Token():
    """FBSP message token generator.
    """
    def __init__(self, value: int=0):
        self._value: int = value
    def next(self) -> bytes:
        """Returns next message token.
        """
        result = pack('!Q', self._value)
        self._value += 1
        return result

class ServiceClient:
    """Base class for Firebird Butler Service clients.
    """
    def __init__(self, timeout: int=1000):
        """
        Arguments:
            timeout: The timeout (in milliseconds) to wait for message.
        """
        self.token: Token = Token()
        self.timeout: int = timeout
        self.channel: Channel = None
        self.session: FBSPSession = None
        self.protocol: FBSPClient = None
    def open(self, channel: Channel, address: ZMQAddress, agent: AgentDescriptor,
             peer_uid: UUID) -> None:
        """Open connection to Firebird Butler service.

        Arguments:
            channel: Channel used for communication with service.
            address: Service endpoint address.
            agent: Client agent identification.
            peer_uid: Client peer ID.
        """
        assert isinstance(channel.protocol, FBSPClient)
        self.channel = channel
        self.session = channel.connect(address)
        self.protocol = channel.protocol
        self.protocol.send_hello(channel, self.session, agent,
                                 PeerDescriptor(peer_uid, os.getpid(), platform.node()),
                                 self.token.next())
        msg = self.channel.receive(self.timeout)
        if isinstance(msg, ErrorMessage):
            raise self.protocol.exception_for(msg)
        elif msg is TIMEOUT:
            raise TimeoutError()
        elif msg is INVALID:
            raise Error("Invalid response from service")
        elif not isinstance(msg, WelcomeMessage):
            raise Error(f"Unexpected {msg.msg_type.name} message from service")
    def send(self, msg: FBSPMessage) -> None:
        """Send message to the service.

        Arguments:
            msg: Message to be sent.
        """
        self.channel.send(msg, self.session)
    def receive(self) -> FBSPMessage:
        """Receive one message from service.

        Raises:
            TimeoutError: When timeout expires.
            Error: When `Channel.receive()` returns INVALID sentinel, or service closes
                   connection with CLOSE message.
        """
        msg = self.channel.receive(self.timeout)
        if isinstance(msg, ErrorMessage):
            raise self.protocol.exception_for(msg)
        elif msg is TIMEOUT:
            raise TimeoutError()
        elif msg is INVALID:
            raise Error("Invalid response from service")
        elif msg.msg_type is MsgType.CLOSE:
            raise Error("Connection closed by service")
        return msg
    def close(self) -> None:
        """Close connection to service.
        """
        self.protocol.send_close(self.channel, self.session)
        self.channel.discard_session(self.session)
        self.session = None
        self.channel = None
    @property
    def connected(self) -> bool:
        """True if client is connected to service.
        """
        return (self.session is not None) and (self.session.greeting is not None)



