# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/base/types.py
# DESCRIPTION:    Saturnin type definitions and constants
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

"""Saturnin common type definitions and constants

This module contains:

1. Type aliases and new types for type annotations.
2. Commonly used constants like platform, vendor and mime type identifiers.
3. Exceptions.
4. Sentinels.
5. Enums.
6. Dataclasses.
"""

from __future__ import annotations

import uuid
from collections.abc import ByteString, Callable
from dataclasses import dataclass, field
from dataclasses import replace as _dcls_replace
from enum import Enum, IntEnum, IntFlag, auto
from typing import TYPE_CHECKING, Any, Final, NewType, TypeAlias, Self

import zmq

from firebird.base.config import Config
from firebird.base.protobuf import PROTO_STRUCT, create_message, dict2struct, load_registered, struct2dict
from firebird.base.strconv import register_convertor
from firebird.base.types import MIME, Distinct, Error, Sentinel
from packaging.specifiers import SpecifierSet

if TYPE_CHECKING:
    from firebird.butler.fbsd_pb2 import PeerIdentification

# Type annotation types
TSupplement: TypeAlias = dict[str, Any] | None
"""name/value dictionary"""
Token = NewType('Token', ByteString)
"""Message token"""
RoutingID = NewType('RoutingID', ByteString)
"""Routing ID"""
GenericCallable: TypeAlias = Callable[..., Any]
"""Generic callable type"""

# Constants
#: Platform OID (`firebird.butler.platform.saturnin`)
PLATFORM_OID: Final[str] = '1.3.6.1.4.1.53446.1.1.0'
#: Platform UID (:func:`~uuid.uuid5` - NAMESPACE_OID)
PLATFORM_UID: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_OID, PLATFORM_OID)
#: Platform version (semver)
PLATFORM_VERSION: Final[str] = '0.8.0'
#: Platform vendor OID (`firebird.butler.vendor.firebird`)
VENDOR_OID: Final[str] = '1.3.6.1.4.1.53446.1.2.0'
#: Platform vendor UID (:func:`~uuid.uuid5` - NAMESPACE_OID)
VENDOR_UID: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_OID, VENDOR_OID)

#: MIME type for protobuf messages
MIME_TYPE_PROTO: Final[MIME] = MIME('application/x.fb.proto')
#: MIME type for plain text
MIME_TYPE_TEXT: Final[MIME] = MIME('text/plain')
#: MIME type for binary data
MIME_TYPE_BINARY: Final[MIME] = MIME('application/octet-stream')

#: Configuration section name for local service addresses
SECTION_LOCAL_ADDRESS: Final[str] = 'local_address'
#: Configuration section name for node service addresses
SECTION_NODE_ADDRESS: Final[str] = 'node_address'
#: Configuration section name for network service addresses
SECTION_NET_ADDRESS: Final[str] = 'net_address'
#: Configuration section name for service UIDs
SECTION_SERVICE_UID: Final[str] = 'service_uid'
#: Configuration section name for service peer UIDs
SECTION_PEER_UID: Final[str] = 'peer_uid'
#: Default configuration section name for service bundle
SECTION_BUNDLE: Final[str] = 'bundle'
#: Default configuration section name for single service
SECTION_SERVICE: Final[str] = 'service'

#: protobuf ID for peer information message
PROTO_PEER: Final[str] = 'firebird.butler.PeerIdentification'

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
    "Exception that should stop further processing."

class RestartError(Error):
    "Exception signaling that restart is needed for further processing."

#Sentinels
#: Sentinel for return values that indicates failed message processing
INVALID: Final[Sentinel] = Sentinel('INVALID')
#: Sentinel for return values that indicates timeout expiration
TIMEOUT: Final[Sentinel] = Sentinel('TIMEOUT')
#: Sentinel for return values that indicates restart request
RESTART: Final[Sentinel] = Sentinel('RESTART')

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
        """Returns the peer's role, which is the logical opposite of this instance's role.

        For example, if this origin is `Origin.SERVICE` (or `Origin.PROVIDER`),
        the peer's role returned will be `Origin.CLIENT` (or `Origin.CONSUMER`).
        If this origin is `Origin.ANY` or `Origin.UNKNOWN`, it returns itself.
        """
        if self in (Origin.ANY, Origin.UNKNOWN):
            return self
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
        "Returns interface UUID."
        raise NotImplementedError()

# Dataclasses
@dataclass(eq=True, order=False, frozen=True)
class ComponentSpecification(Distinct):
    """Component specification dataclass.

    Arguments:
        uid: Component ID
        version_spec: Component version specification
    """
    uid: uuid.UUID
    version_spec: SpecifierSet = None
    def get_key(self) -> uuid.UUID:
        """Returns `uid` (instance key). Used for instance hash computation."""
        return self.uid
    def copy(self) -> Self:
        """Returns copy of this ComponentSpecification instance.
        """
        return _dcls_replace(self)
    def replace(self, **changes) -> Self:
        """Creates a new `ComponentSpecification`, replacing fields with values from `changes`.
        """
        return _dcls_replace(self, **changes)

@dataclass(eq=True, order=False, frozen=True)
class AgentDescriptor(Distinct):
    """Service or Client descriptor dataclass.

    Arguments:
        uid: Agent ID
        name: Agent name
        version: Agent version string
        vendor_uid: Vendor ID
        classification: Agent classification string
        platform_uid: Butler platform ID
        platform_version: Butler platform version string
        supplement: Optional list of supplemental information
    """
    uid: uuid.UUID
    name: str
    version: str
    vendor_uid: uuid.UUID
    classification: str
    platform_uid: uuid.UUID = PLATFORM_UID
    platform_version: str = PLATFORM_VERSION
    supplement: TSupplement = None
    def get_key(self) -> uuid.UUID:
        """Returns `uid` (instance key). Used for instance hash computation."""
        return self.uid
    def copy(self) -> Self:
        """Returns copy of this AgentDescriptor instance.
        """
        return _dcls_replace(self)
    def replace(self, **changes) -> Self:
        """Creates a new `AgentDescriptor`, replacing fields with values from `changes`.
        """
        return _dcls_replace(self, **changes)

@dataclass(eq=True, order=False, frozen=True)
class PeerDescriptor(Distinct):
    """Peer descriptor.

    Arguments:
       uid: Peer ID
       pid: Peer process ID
       host: Host name
       supplement: Optional list of supplemental information
    """
    uid: uuid.UUID
    pid: int
    host: str
    supplement: TSupplement = None
    def get_key(self) -> uuid.UUID:
        """Returns `uid` (instance key). Used for instance hash computation."""
        return self.uid
    def as_proto(self) -> Any:
        """Returns `firebird.butler.PeerIdentification` protobuf message initialized
        from instance data.
        """
        msg: PeerIdentification = create_message(PROTO_PEER)
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
    def replace(self, **changes) -> Self:
        """Creates a new `PeerDescriptor`, replacing fields with values from `changes`.
        """
        return _dcls_replace(self, **changes)
    @classmethod
    def from_proto(cls, proto: Any) -> Self:
        """Creates new PeerDescriptor from `firebird.butler.PeerIdentification` protobuf
        message.
        """
        if proto.DESCRIPTOR.full_name != PROTO_PEER:
            raise ValueError("PeerIdentification protobuf message required")
        data = None
        if proto.supplement:
            for i in proto.supplement:
                if i.TypeName() == PROTO_STRUCT:
                    msg = create_message(PROTO_STRUCT)
                    i.Unpack(msg)
                    data = struct2dict(msg)
                    break
        return cls(uuid.UUID(bytes=proto.uid), proto.pid, proto.host, data)

@dataclass(eq=True, order=False, frozen=True)
class ServiceDescriptor(Distinct):
    """Service descriptor.

    Arguments:
       agent: Service agent descriptor
       api: Service FBSP API description or `None` for microservice
       description: Text describing the service
       facilities: List of Saturnin facilities that this service uses
       factory: Locator string for service factory (e.g. like 'my_package.my_module:my_svc_factory_class')
       config: Service configuration factory (a callable that returns a `Config` object)
    """
    agent: AgentDescriptor
    api: list[ButlerInterface]
    description: str
    facilities: list[str]
    factory: str
    config: Callable[[], Config]
    def get_key(self) -> uuid.UUID:
        """Returns `agent.uid` (instance key). Used for instance hash computation."""
        return self.agent.uid

@dataclass(eq=True, order=False, frozen=True)
class ApplicationDescriptor(Distinct):
    """Application descriptor.

    Arguments:
       uid: Application ID
       name: Application name
       version: Application version string
       vendor_uid: Vendor ID
       classification: Application classification string
       description: Text describing the application
       cli_command: Locator string for application `typer` command (e.g. like 'my_app.cli:app_cmd')
       recipe_factory: Locator string for application recipe factory (a callable that returns string)
    """
    uid: uuid.UUID
    name: str
    version: str
    vendor_uid: uuid.UUID
    classification: str
    description: str
    cli_command: str | None = None
    recipe_factory: str | None = None
    def get_key(self) -> uuid.UUID:
        """Returns `uid` (instance key). Used for instance hash computation."""
        return self.uid


@dataclass(order=True)
class PrioritizedItem:
    """Prioritized item for use with `heapq` to implement priority queue.

    Arguments:
       priority: Item priority
       item: Prioritized item
    """
    priority: int
    item: Any=field(compare=False)

load_registered('firebird.butler.protobuf')
load_registered('firebird.base.protobuf')
del load_registered
register_convertor(SpecifierSet)
del register_convertor
