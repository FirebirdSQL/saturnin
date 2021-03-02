#coding:utf-8
#
# PROGRAM/MODULE: saturnin-core
# FILE:           saturnin/core/types.py
# DESCRIPTION:    Type definitions
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

"""Saturnin - Type definitions
"""

from __future__ import annotations
from typing import List, Dict, Optional, NewType, Callable, Any
from enum import IntEnum, IntFlag, Enum, auto
import uuid
import zmq
from dataclasses import dataclass, field, replace as _dcls_replace
from firebird.base.types import Error, Distinct, MIME, Sentinel
from firebird.base.protobuf import PROTO_STRUCT, load_registered, create_message, \
     struct2dict, dict2struct

# Type annotation types
TSupplement = Optional[Dict[str, Any]]
"""name/value dictionary"""
Token = NewType('Token', bytearray)
"""Message token"""
RoutingID = NewType('RoutingID', bytes)
"""Routing ID"""

# Constants
PLATFORM_OID: str = '1.3.6.1.4.1.53446.1.2.0'
"Platform OID (`firebird.butler.platform.saturnin`)"
PLATFORM_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, PLATFORM_OID)
"Platform UID (:func:`~uuid.uuid5` - NAMESPACE_OID)"
PLATFORM_VERSION: str = '0.6.0'
"Platform version (semver)"

VENDOR_OID: str = '1.3.6.1.4.1.53446.1.3.0'
"Platform vendor OID (`firebird.butler.vendor.firebird`)"
VENDOR_UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, VENDOR_OID)
"Platform vendor UID (:func:`~uuid.uuid5` - NAMESPACE_OID)"

MIME_TYPE_PROTO = MIME('application/x.fb.proto')
MIME_TYPE_TEXT = MIME('text/plain')
MIME_TYPE_BINARY = MIME('application/octet-stream')

PROTO_PEER = 'firebird.butler.PeerIdentification'

#  Exceptions
class InvalidMessageError(Error):
    "A formal error was detected in a message"
class ChannelError(Error):
    "Transmission channel error"
class ServiceError(Error):
    "Error raised by service"
class ClientError(Error):
    "Error raised by Client"
class StopError(Error):
    "Error that should stop furter processing."

#Sentinels
#: Sentinel for return values that indicates failed message processing
INVALID: Sentinel = Sentinel('INVALID')
#: Sentinel for return values that indicates timeout expiration
TIMEOUT: Sentinel = Sentinel('TIMEOUT')

# Enums
class Origin(IntEnum):
    """Origin of received message in protocol context."""
    UNKNOWN = auto()
    SERVICE = auto()
    CLIENT = auto()
    ANY = auto()
    # Aliases
    PROVIDER = SERVICE
    CONSUMER = CLIENT
    def peer_role(self) -> Origin:
        if self == Origin.ANY:
            return self
        else:
            return Origin.CLIENT if self == Origin.SERVICE else Origin.SERVICE

class SocketMode(IntEnum):
    """ZeroMQ socket mode."""
    UNKNOWN = auto()
    BIND = auto()
    CONNECT = auto()

class Direction(IntFlag):
    """ZeroMQ socket direction of transmission."""
    NONE = 0
    IN = zmq.POLLIN
    OUT = zmq.POLLOUT
    BOTH = OUT | IN

class SocketType(IntEnum):
    """ZeroMQ socket type."""
    UNKNOWN_TYPE = -1 # Not a valid option, defined only to handle undefined values
    DEALER = zmq.DEALER
    ROUTER = zmq.ROUTER
    PUB = zmq.PUB
    SUB = zmq.SUB
    XPUB = zmq.XPUB
    XSUB = zmq.XSUB
    PUSH = zmq.PUSH
    PULL = zmq.PULL
    STREAM = zmq.STREAM
    PAIR = zmq.PAIR

class State(IntEnum):
    """General state information."""
    UNKNOWN_STATE = 0
    READY = 1
    RUNNING = 2
    WAITING = 3
    SUSPENDED = 4
    FINISHED = 5
    ABORTED = 6
    # Aliases
    CREATED = READY
    BLOCKED = WAITING
    STOPPED = SUSPENDED
    TERMINATED = ABORTED

class PipeSocket(IntEnum):
    """Data Pipe Socket identification."""
    UNKNOWN_PIPE_SOCKET = 0 # Not a valid option, defined only to handle undefined values
    INPUT = 1
    OUTPUT = 2

class FileOpenMode(IntEnum):
    """File open mode."""
    UNKNOWN_FILE_OPEN_MODE = 0 # Not a valid option, defined only to handle undefined values
    READ = 1
    CREATE = 2
    WRITE = 3
    APPEND = 4
    RENAME = 5

class Outcome(Enum):
    """Service execution outcome.
    """
    UNKNOWN = 'UNKNOWN'
    OK = 'OK'
    ERROR = 'ERROR'

class ButlerInterface(IntEnum):
    """Base class for service API code enumerations (FBSP interfaces).
    """
    @classmethod
    def get_uid(cls) -> uuid.UUID:
        raise NotImplementedError()

# Dataclasses
@dataclass(eq=True, order=False, frozen=True)
class AgentDescriptor(Distinct):
    """Service or Client descriptor dataclass.

    Note:
        Because this is a `dataclass`, the class variables are those attributes that have
        default value. Other attributes are created in constructor.
    """
    #: Agent ID
    uid: uuid.UUID
    #: Agent name
    name: str
    #: Agent version string
    version: str
    #: Vendor ID
    vendor_uid: uuid.UUID
    #: Agent classification string
    classification: str
    #: Butler platform ID
    platform_uid: uuid.UUID = PLATFORM_UID
    #: Butler platform version string
    platform_version: str = PLATFORM_VERSION
    #: Optional list of supplemental information
    supplement: TSupplement = None
    def get_key(self) -> Any:
        """Returns `uid` (instance key). Used for instance hash computation."""
        return self.uid
    def copy(self) -> AgentDescriptor:
        """Returns copy of this AgentDescriptor instance.
        """
        return _dcls_replace(self)
    def replace(self, **changes) -> AgentDescriptor:
        """Creates a new `AgentDescriptor`, replacing fields with values from `changes`.
        """
        return _dcls_replace(self, **changes)

@dataclass(eq=True, order=False, frozen=True)
class PeerDescriptor(Distinct):
    """Peer descriptor.
    """
    #: Peer ID
    uid: uuid.UUID
    #: Peer process ID
    pid: int
    #: Host name
    host: str
    #: Optional list of supplemental information
    supplement: TSupplement = None
    def get_key(self) -> Any:
        """Returns `uid` (instance key). Used for instance hash computation."""
        return self.uid
    def as_proto(self) -> Any:
        """Returns `firebird.butler.PeerIdentification` protobuf message initialized
        from instance data.
        """
        msg = create_message(PROTO_PEER)
        msg.uid = self.uid.bytes
        msg.pid = self.pid
        msg.host = self.host
        if self.supplement is not None:
            sup = msg.supplement.add()
            sup.Pack(dict2struct(self.supplement))
        return msg
    def copy(self) -> PeerDescriptor:
        """Returns copy of this PeerDescriptor instance.
        """
        return _dcls_replace(self)
    def replace(self, **changes) -> PeerDescriptor:
        """Creates a new `PeerDescriptor`, replacing fields with values from `changes`.
        """
        return _dcls_replace(self, **changes)
    @classmethod
    def from_proto(cls, proto: Any) -> PeerDescriptor:
        """Creates new PeerDescriptor from `firebird.butler.PeerIdentification` protobuf
        message.
        """
        if proto.DESCRIPTOR.full_name != PROTO_PEER:
            raise ValueError("PeerIdentification protobuf message required")
        data = None
        if proto.supplement:
            for i in proto.supplement:
                if i.TypeName() == PROTO_STRUCT:
                    s = create_message(PROTO_STRUCT)
                    i.Unpack(s)
                    data = struct2dict(s)
                    break
        return cls(uuid.UUID(bytes=proto.uid), proto.pid, proto.host, data)

@dataclass(eq=True, order=False, frozen=True)
class ServiceDescriptor(Distinct):
    """Service descriptor.
    """
    #: Service agent descriptor
    agent: AgentDescriptor
    #: Service FBSP API description or `None` for microservice
    api: List[ButlerInterface]
    #: Text describing the service
    description: str
    #: List of Saturnin facilities that this service uses
    facilities: List[str]
    #: Python package that contains this service
    package: str
    #: Locator string for service factory
    factory: str
    #: Service configuration factory
    config: Callable[[], 'firebird.base.config.Config']
    def get_key(self) -> Any:
        """Returns `agent.uid` (instance key). Used for instance hash computation."""
        return self.agent.uid

@dataclass(order=True)
class PrioritizedItem:
    """Prioritized item for use with `heapq` to implement priority queue.
    """
    priority: int
    item: Any=field(compare=False)

load_registered('firebird.butler.protobuf')
load_registered('firebird.base.protobuf')
del load_registered
