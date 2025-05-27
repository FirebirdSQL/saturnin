# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/protocol/fbsp.py
# DESCRIPTION:    Firebird Butler Service Protocol
#                 See https://firebird-butler.readthedocs.io/en/latest/rfc/4/FBSP.html
# CREATED:        21.2.2019
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

"""Saturnin reference implementation of Firebird Butler Service Protocol.

See https://firebird-butler.readthedocs.io/en/latest/rfc/4/FBSP.html
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from contextlib import suppress
from enum import IntEnum, IntFlag
from struct import pack, unpack
from traceback import format_exception
from typing import TYPE_CHECKING, Any, ClassVar, Final

import zmq
from saturnin.base import (
    ANY,
    INVALID,
    AgentDescriptor,
    ButlerInterface,
    Channel,
    InvalidMessageError,
    Message,
    PeerDescriptor,
    Protocol,
    RoutingID,
    ServiceDescriptor,
    ServiceError,
    Session,
    State,
    StopError,
    Token,
    TZMQMessage,
)

from firebird.base.protobuf import ProtoMessage, create_message
from firebird.base.signal import eventsocket

if TYPE_CHECKING:
    from firebird.butler.fbsd_pb2 import ErrorDescription
    from firebird.butler.fbsp_pb2 import (
        FBSPCancelRequests,
        FBSPHelloDataframe,
        FBSPStateInformation,
        FBSPWelcomeDataframe,
    )

# Message header
#: FBSP protocol control frame :mod:`struct` format
HEADER_FMT_FULL: Final[str] = '!4sBBH8s'
#: FBSP protocol control frame :mod:`struct` format without FOURCC
HEADER_FMT: Final[str] = '!4xBBH8s'
#: FBSP protocol identification (FOURCC)
FOURCC: Final[bytes] = b'FBSP'
#: FBSP protocol version mask
VERSION_MASK: Final[int] = 7
#: FBSP protocol error mask
ERROR_TYPE_MASK: Final[int] = 31

# Protobuf messages

#: Protobuf message for FBSP HELLO message
PROTO_HELLO: Final[str] = 'firebird.butler.FBSPHelloDataframe'
#: Protobuf message for FBSP WELCOME message
PROTO_WELCOME: Final[str] = 'firebird.butler.FBSPWelcomeDataframe'
#: Protobuf message for FBSP CANCEL REQUEST message
PROTO_CANCEL_REQ: Final[str] = 'firebird.butler.FBSPCancelRequests'
#: Protobuf message for FBSP STATE INFO message
PROTO_STATE_INFO: Final[str] = 'firebird.butler.FBSPStateInformation'
#: Protobuf message for FBSP ERROR message
PROTO_ERROR: Final[str] = 'firebird.butler.ErrorDescription'

# Enums

class MsgType(IntEnum):
    """FBSP Message Type"""
    UNKNOWN = 0 # Not a valid option, defined only to handle undefined values
    HELLO = 1   # initial message from client
    WELCOME = 2 # initial message from service
    NOOP = 3    # no operation, used for keep-alive & ping purposes
    REQUEST = 4 # client request
    REPLY = 5   # service response to client request
    DATA = 6    # separate data sent by either client or service
    CANCEL = 7  # cancel request
    STATE = 8   # operating state information
    CLOSE = 9   # sent by peer that is going to close the connection
    ERROR = 31  # error reported by service

class MsgFlag(IntFlag):
    """FBSP message flag"""
    NONE = 0
    ACK_REQ = 1
    ACK_REPLY = 2
    MORE = 4

class ErrorCode(IntEnum):
    """FBSP Error Code"""
    # Errors indicating that particular request cannot be satisfied
    INVALID_MESSAGE = 1
    PROTOCOL_VIOLATION = 2
    BAD_REQUEST = 3
    NOT_IMPLEMENTED = 4
    ERROR = 5
    INTERNAL_ERROR = 6
    REQUEST_TIMEOUT = 7
    TOO_MANY_REQUESTS = 8
    FAILED_DEPENDENCY = 9
    FORBIDDEN = 10
    UNAUTHORIZED = 11
    NOT_FOUND = 12
    GONE = 13
    CONFLICT = 14
    PAYLOAD_TOO_LARGE = 15
    INSUFFICIENT_STORAGE = 16
    REQUEST_CANCELLED = 17
    # Fatal errors indicating that connection would/should be terminated
    SERVICE_UNAVAILABLE = 2000
    FBSP_VERSION_NOT_SUPPORTED = 2001

def bb2h(value_hi: int, value_lo: int) -> int:
    """Compose two bytes (high byte, low byte) into a 16-bit unsigned word (short) value
    using network byte order (big-endian).
    """
    return unpack('!H', pack('!BB', value_hi, value_lo))[0]

def msg_bytes(msg: bytes | bytearray | zmq.Frame) -> bytes | bytearray:
    """Return message frame as bytes.
    """
    return msg.bytes if isinstance(msg, zmq.Frame) else msg

class FBSPMessage(Message):
    """Firebird Butler Service Protocol (FBSP) Message.
    """
    def __init__(self):
        #: Type of message
        self.msg_type: MsgType = MsgType.UNKNOWN
        #: Message flags
        self.flags: MsgFlag = MsgFlag.NONE
        #: Data associated with message
        self.type_data: int = 0
        #: Message token
        self.token: Token = bytearray(8)
    def __str__(self):
        return f"{self.__class__.__qualname__}[{self.msg_type.name}]"
    __repr__ = __str__
    def _unpack_data(self, data: list) -> None:
        """Called when all fields of the message are set. Usefull for data deserialization.

        Note: Default implementation does nothing.

        Arguments:
            data: A list of remaining ZMQ frames after the header, to be deserialized into
                  message-specific attributes.
        """
    def _pack_data(self) -> list:
        """Called when serialization is requested.

        Note: Default implementation returns empty list.

        Returns:
            A list of ZMQ-compatible frames (bytes or zmq.Frame) representing the message-specific payload.
        """
        return []
    def _set_hdr(self, header: bytes) -> None:
        """Initialize new message from header.
        """
        control_byte, flags, self.type_data, self.token = unpack(HEADER_FMT, header)
        self.msg_type = MsgType(control_byte >> 3)
        self.flags = MsgFlag(flags)
    def from_zmsg(self, zmsg: TZMQMessage) -> None:
        """Populate message data from sequence of ZMQ data frames.

        Arguments:
            zmsg: Sequence of ZMQ frames. The first frame (header) is assumed to
                  have been pre-processed by the message factory to set initial
                  attributes like `msg_type`. This method processes subsequent frames.

        Raises:
            InvalidMessageError: If message is not a valid protocol message.
        """
        try:
            zmsg.pop(0) # header is already set by message_factory
            if MsgFlag.ACK_REPLY not in self.flags:
                self._unpack_data(zmsg)
        except Exception as exc:
            raise InvalidMessageError("Invalid message") from exc
    def as_zmsg(self) -> TZMQMessage:
        """Returns message as sequence of ZMQ data frames.
        """
        zmsg = [self.get_header()]
        if MsgFlag.ACK_REPLY not in self.flags:
            zmsg.extend(self._pack_data())
        return zmsg
    def clear(self) -> None:
        """Clears message data.

        Important:
            The `msg_type` remains the same (i.e. you can't change the message type once
            message instance was created), but all other data are cleared.
        """
        self.type_data = 0
        self.flags = MsgFlag(0)
        self.token: Token = bytearray(8)
    def copy(self) -> Message:
        """Returns copy of the message.
        """
        msg: FBSPMessage = self.__class__()
        msg.from_zmsg(self.as_zmsg())
        return msg
    def get_keys(self) -> Iterable:
        """Returns iterable of dictionary keys to be used with `Protocol.handlers`.
        Keys must be provided in order of precedence (from more specific to general).
        """
        return [self.msg_type, ANY]
    def get_header(self) -> bytes:
        """Return message header (FBSP control frame).
        """
        return pack(HEADER_FMT_FULL, FOURCC, (self.msg_type << 3) | 1, self.flags,
                    self.type_data, self.token)
    def has_more(self) -> bool:
        """Returns True if message has `MORE` flag set.
        """
        return MsgFlag.MORE in self.flags
    def has_ack_req(self) -> bool:
        """Returns True if message has ACK_REQ flag set.
        """
        return MsgFlag.ACK_REQ in self.flags
    def has_ack_reply(self) -> bool:
        """Returns True if message has ASK_REPLY flag set.
        """
        return MsgFlag.ACK_REPLY in self.flags
    def set_flag(self, flag: MsgFlag) -> None:
        """Set flag specified by `flag` mask.
        """
        self.flags |= flag
    def clear_flag(self, flag: MsgFlag) -> None:
        """Clear flag specified by `flag` mask.
        """
        self.flags &= ~flag

class HandshakeMessage(FBSPMessage):
    """Base FBSP client/service handshake message (`HELLO` or `WELCOME`). The message
    includes basic information about the Peer.
    """
    def __init__(self):
        super().__init__()
        #: Protobuf message instance holding peer information.
        self.data: ProtoMessage = None
    def _unpack_data(self, data: list) -> None:
        """Called when all fields of the message are set. Usefull for data deserialization.
        """
        self.data.ParseFromString(data.pop(0))
    def _pack_data(self) -> list:
        """Called when serialization is requested.
        """
        return [self.data.SerializeToString()]
    def clear(self) -> None:
        """Clears message attributes.
        """
        super().clear()
        self.data.Clear()

class HelloMessage(HandshakeMessage):
    """The `HELLO` message is a Client request to open a Connection to the Service.
    The message includes basic information about the Client and Connection parameters
    required by the Client.
    """
    def __init__(self):
        super().__init__()
        #:`FBSPHelloDataframe` protobuf message with peer information
        self.data: FBSPHelloDataframe = create_message(PROTO_HELLO)

class WelcomeMessage(HandshakeMessage):
    """The `WELCOME` message is the response of the Service to the `HELLO` message sent by
    the Client, which confirms the successful creation of the required Connection and announces
    basic parameters of the Service and the Connection.
    """
    def __init__(self):
        super().__init__()
        #: `FBSPWelcomeDataframe` protobuf message with peer information
        self.data: FBSPWelcomeDataframe = create_message(PROTO_WELCOME)

class APIMessage(FBSPMessage):
    """Base FBSP client/service API message (`REQUEST`, `REPLY`, `STATE`).
    The message includes information about the API call (interface ID and API Code).
    """
    def __init__(self):
        super().__init__()
        #: List of bytes, typically representing data frames of the API message payload.
        self.data: list = []
    def _unpack_data(self, data: list) -> None:
        """Called when all fields of the message are set. Usefull for data deserialization.
        """
        self.data.extend(i.bytes if isinstance(i, zmq.Frame) else i for i in data)
    def _pack_data(self) -> list:
        """Called when serialization is requested.
        """
        return self.data
    def clear(self) -> None:
        """Clears message attributes.
        """
        super().clear()
        self.data.clear()
    @property
    def interface_id(self) -> int:
        "Interface ID (high byte of Request Code)"
        return unpack('!BB', pack('!H', self.type_data))[0]
    @interface_id.setter
    def interface_id(self, value: int) -> None:
        self.type_data = bb2h(value, self.api_code)
    @property
    def api_code(self) -> int:
        "API Code (lower byte of Request Code)"
        return unpack('!BB', pack('!H', self.type_data))[1]
    @api_code.setter
    def api_code(self, value: int) -> None:
        self.type_data = bb2h(self.interface_id, value)
    @property
    def request_code(self) -> int:
        "Request Code (Interface ID + API Code)"
        return self.type_data

class StateMessage(APIMessage):
    """The `STATE` message is a Client request to the Service.
    """
    def __init__(self):
        super().__init__()
        #: `FBSPStateInformation` protobuf message with state information
        self.state_info: FBSPStateInformation = create_message(PROTO_STATE_INFO)
    def _unpack_data(self, data: list) -> None:
        """Called when all fields of the message are set. Usefull for data deserialization.

        Arguments:
            data: A list containing the serialized `FBSPStateInformation` protobuf message.
        """
        self.state_info.ParseFromString(data.pop(0))
        super()._unpack_data(data)
    def _pack_data(self) -> list:
        """Called when serialization is requested.

        Returns:
            A list containing the serialized `FBSPStateInformation` protobuf message.
        """
        return [self.state_info.SerializeToString()]
    def clear(self) -> None:
        """Clears message attributes.
        """
        super().clear()
        self.state_info.Clear()
    @property
    def state(self) -> State:
        "Service state"
        return State(self.state_info.state)
    @state.setter
    def state(self, value: State) -> None:
        self.state_info.state = value.value

class DataMessage(FBSPMessage):
    """The `DATA` message is intended for delivery of arbitrary data between connected peers."""
    def __init__(self):
        super().__init__()
        #: Data payload
        self.data: list[bytes] = []
    def _unpack_data(self, data: list) -> None:
        """Called when all fields of the message are set. Usefull for data deserialization.

        Arguments:
            data: A list containing `bytes` or `zmq.Frame` data payload.
        """
        self.data.extend(i.bytes if isinstance(i, zmq.Frame) else i for i in data)
    def _pack_data(self) -> list:
        """Called when serialization is requested.

        Returns:
            A list of `bytes` containing the message `data`.
        """
        return self.data
    def clear(self) -> None:
        """Clears message attributes.
        """
        super().clear()
        self.data.clear()

class CancelMessage(FBSPMessage):
    """The `CANCEL` message represents a request for a Service to stop processing the previous
    request from the Client.
    """
    def __init__(self):
        super().__init__()
        #: `.FBSPCancelRequests` protobuf message
        self.request: FBSPCancelRequests = create_message(PROTO_CANCEL_REQ)
    def _unpack_data(self, data: list) -> None:
        """Called when all fields of the message are set. Usefull for data deserialization.

        Arguments:
            data: A list containing the serialized `FBSPCancelRequests` protobuf message.
        """
        self.request.ParseFromString(data.pop(0))
    def _pack_data(self) -> list:
        """Called when serialization is requested.

        Returns:
            A list containing the serialized `FBSPCancelRequests` protobuf message.
        """
        return [self.request.SerializeToString()]
    def clear(self) -> None:
        """Clears message attributes.
        """
        super().clear()
        self.request.Clear()

class ErrorMessage(FBSPMessage):
    """The `ERROR` message notifies the Client about error condition detected by Service.
    """
    def __init__(self):
        super().__init__()
        #: List of `.ErrorDescription` protobuf messages with error information
        self.errors: list[ErrorDescription] = []
    def _unpack_data(self, data: list) -> None:
        """Called when all fields of the message are set. Usefull for data deserialization.

        Arguments:
            data: A list containing the serialized `ErrorDescription` protobuf messages.
        """
        while data:
            err = create_message(PROTO_ERROR)
            err.ParseFromString(msg_bytes(data.pop(0)))
            self.errors.append(err)
    def _pack_data(self) -> list:
        """Called when serialization is requested.

        Returns:
            A list containing the serialized `ErrorDescription` protobuf messages.
        """
        return [err.SerializeToString() for err in self.errors]
    def clear(self) -> None:
        """Clears message attributes.
        """
        super().clear()
        self.errors.clear()
    def add_error(self) -> ErrorDescription:
        """Return newly created `ErrorDescription` associated with message."""
        err = create_message(PROTO_ERROR)
        self.errors.append(err)
        return err
    def note_exception(self, exc: Exception) -> None:
        """Store information from exception into `.ErrorMessage`.

        Arguments:
            exc: The Exceptioninstance to be recorded in the error message. Handles chained
                 exceptions viacause `cause` attribute.
        """
        to_note = exc
        while to_note:
            errdesc = self.add_error()
            if hasattr(to_note, 'code'):
                errdesc.code = to_note.code
            errdesc.description = str(to_note)
            if not isinstance(to_note, StopError):
                errdesc.annotation['traceback'] = \
                    ''.join(format_exception(to_note.__class__, to_note,
                                             to_note.__traceback__, chain=False))
            to_note = to_note.__cause__
    @property
    def error_code(self) -> ErrorCode:
        "Error code"
        return ErrorCode(self.type_data >> 5)
    @error_code.setter
    def error_code(self, value: ErrorCode) -> None:
        self.type_data = (value.value << 5) | (self.type_data & ERROR_TYPE_MASK)
    @property
    def relates_to(self) -> MsgType:
        "Message type this error relates to"
        return MsgType(self.type_data & ERROR_TYPE_MASK)
    @relates_to.setter
    def relates_to(self, value: MsgType) -> None:
        self.type_data &= ~ERROR_TYPE_MASK
        self.type_data |= value.value

class _FBSP(Protocol):
    """4/FBSP - Firebird Butler Service Protocol
    """
    #: string with protocol OID (dot notation).
    OID: Final[str] =  '1.3.6.1.4.1.53446.1.3.1'
    # iso.org.dod.internet.private.enterprise.firebird.butler.protocol.fbsp
    #: UUID instance that identifies the protocol.
    UID: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_OID, OID)
    #: Mapping from message type to specific Message class
    MESSAGE_MAP: ClassVar[dict[MsgType, FBSPMessage]] = {
        MsgType.HELLO: HelloMessage,
        MsgType.WELCOME: WelcomeMessage,
        MsgType.NOOP: FBSPMessage,
        MsgType.REQUEST: APIMessage,
        MsgType.REPLY: APIMessage,
        MsgType.DATA: DataMessage,
        MsgType.CANCEL: CancelMessage,
        MsgType.STATE: StateMessage,
        MsgType.CLOSE: FBSPMessage,
        MsgType.ERROR: ErrorMessage,
    }
    def __init__(self, *, session_type: type[Session]):
        """
        Arguments:
            session_type: Class for session objects.
        """
        super().__init__(session_type=session_type)
        self.message_factory = self.__message_factory
    def __message_factory(self, zmsg: TZMQMessage | None=None) -> Message:
        """Internal message factory.

        Arguments:
            zmsg: The raw ZMQ message list, used here to extract the header for determining
                  message type and initializing the correct `.FBSPMessage` subclass.
        """
        msg = self.MESSAGE_MAP[MsgType(int.from_bytes(zmsg[0][4:5], 'big') >> 3)]()
        msg._set_hdr(zmsg[0])
        return msg
    def validate(self, zmsg: TZMQMessage) -> None:
        """Verifies that sequence of ZMQ data frames is a valid FBSP protocol message.

        If this validation passes without exception, then `.convert_msg()` of the same
        message must be successful as well.

        Arguments:
            zmsg: ZeroMQ multipart message to be validated against FBSP rules (FourCC,
                  version, header structure, type-specific frames).

        Raises:
            InvalidMessageError: If ZMQ message is not a valid FBSP message.
        """
        if not zmsg:
            raise InvalidMessageError("Empty message")
        fbsp_header = zmsg[0]
        if len(fbsp_header) != 16: # noqa: PLR2004
            raise InvalidMessageError("Message header must be 16 bytes long")
        try:
            fourcc, control_byte, flags, type_data, _ = unpack(HEADER_FMT_FULL, fbsp_header)
        except Exception as exp:
            raise InvalidMessageError("Can't parse the control frame") from exp
        if fourcc != FOURCC:
            raise InvalidMessageError("Invalid FourCC")
        if (control_byte & VERSION_MASK) != self.REVISION:
            raise InvalidMessageError("Invalid protocol version")
        if (flags | 7) > 7: # noqa: PLR2004
            raise InvalidMessageError("Invalid flags")
        msg_type = control_byte >> 3
        try:
            if msg_type == 0:
                raise ValueError()
            message_type = MsgType(msg_type)
        except ValueError as exc:
            raise InvalidMessageError(f"Illegal message type {msg_type}") from exc
        #
        if message_type in (MsgType.REQUEST, MsgType.REPLY, MsgType.STATE):
            # Check request_code validity
            pass
        if message_type is MsgType.ERROR:
            try:
                ErrorCode(type_data >> 5)
            except ValueError as exc:
                raise InvalidMessageError(f"Unknown ERROR code: {type_data >> 5}") from exc
            if MsgType(type_data & ERROR_TYPE_MASK) not in (MsgType.UNKNOWN, MsgType.HELLO,
                                                            MsgType.REQUEST, MsgType.DATA,
                                                            MsgType.CANCEL):
                raise InvalidMessageError("Invalid request code in ERROR message")
            if len(zmsg) > 1:
                frame = create_message(PROTO_ERROR)
                for i, segment in enumerate(zmsg[1:]):
                    try:
                        frame.ParseFromString(msg_bytes(segment))
                        frame.Clear()
                    except Exception as exc:
                        raise InvalidMessageError(f"Invalid ERROR message data frame: {i}") from exc
        elif message_type is MsgType.HELLO:
            try:
                create_message(PROTO_HELLO).ParseFromString(msg_bytes(zmsg[1]))
            except Exception as exc:
                raise InvalidMessageError("Invalid HELLO message data frame") from exc
        elif message_type is MsgType.WELCOME:
            try:
                create_message(PROTO_WELCOME).ParseFromString(msg_bytes(zmsg[1]))
            except Exception as exc:
                raise InvalidMessageError("Invalid WELCOME message data frame") from exc
        elif message_type is MsgType.NOOP:
            if len(zmsg) > 1:
                raise InvalidMessageError("Data frames not allowed for NOOP message")
        elif message_type is MsgType.CANCEL:
            if len(zmsg) > 2: # noqa: PLR2004
                raise InvalidMessageError("CANCEL message must have exactly one data frame")
            try:
                create_message(PROTO_CANCEL_REQ).ParseFromString(msg_bytes(zmsg[2]))
            except Exception as exc:
                raise InvalidMessageError("Invalid CANCEL message data frame") from exc
        elif message_type is MsgType.STATE:
            if len(zmsg) > 2:  # noqa: PLR2004
                raise InvalidMessageError("STATE message must have exactly one data frame")
            try:
                create_message(PROTO_STATE_INFO).ParseFromString(msg_bytes(zmsg[2]))
            except Exception as exc:
                raise InvalidMessageError("Invalid STATE message data frame") from exc
    def create_message_for(self, message_type: MsgType, token: Token=bytes(8),
                           type_data: int=0, flags: MsgFlag=MsgFlag.NONE) -> FBSPMessage:
        """Create new `.FBSPMessage` child class instance for particular FBSP message type.

        Arguments:
            message_type: Type of message to be created
            token:        Message token
            type_data:    Message control data
            flags:        Flags

        Returns:
            New `.FBSPMessage` subclass instance, initialized with the provided header details.
        """
        return self.message_factory([pack(HEADER_FMT_FULL, FOURCC, (message_type << 3) | 1,
                                          flags, type_data, token)])
    def create_ack_reply(self, msg: FBSPMessage) -> FBSPMessage:
        """Returns new message that is an ACK-REPLY response message.

        Arguments:
            msg: Message to be acknowledged.
        """
        return self.message_factory([pack(HEADER_FMT_FULL, FOURCC,
                                          (msg.msg_type << 3) | 1,
                                          (msg.flags & ~MsgFlag.ACK_REQ) | MsgFlag.ACK_REPLY,
                                          msg.type_data, msg.token)])
    def create_data_for(self, msg: APIMessage) -> DataMessage:
        """Create new DataMessage for reply to specific reuest message.

        Arguments:
            message: Request message instance that data relates to
        """
        return self.create_message_for(MsgType.DATA, msg.token)

class FBSPSession(Session):
    """FBSP session that holds information about attached peer.
    """
    def __init__(self):
        super().__init__()
        #: `.HelloMessage` (for service sessions) or `.WelcomeMessage` (for client sessions)
        #: received from peer during handshake.
        self.greeting: HelloMessage = None
        #: Client peer ID for service, Service agent ID for client
        self.partner_uid: uuid.UUID = None

class FBSPService(_FBSP):
    """4/FBSP - Firebird Butler Service Protocol - Service side.
    """
    def __init__(self, *, session_type: type[FBSPSession]=FBSPSession,
                 service: ServiceDescriptor, peer: PeerDescriptor):
        """
        Arguments:
            session_type: Class for session objects.
            service: Agent descriptor for service.
            peer: Peer descriptor for service.
        """
        super().__init__(session_type=session_type)
        self.handlers.update({MsgType.HELLO: self.handle_hello_msg,
                              MsgType.REQUEST: self.handle_request_msg,
                              MsgType.CANCEL: self.handle_cancel_msg,
                              MsgType.NOOP: self.handle_noop_msg,
                              MsgType.DATA: self.handle_data_msg,
                              MsgType.CLOSE: self.handle_close_msg,
                              MsgType.REPLY: self.handle_ack_reply,
                              MsgType.STATE: self.handle_ack_reply,
                              MsgType.WELCOME: self.handle_unexpected_msg,
                              })
        self.api_handlers: dict[Any, Callable] = {}
        self._apis: list[ButlerInterface] = []
        self._apis.extend(service.api)
        self.welcome_df: FBSPWelcomeDataframe = create_message(PROTO_WELCOME)
        self.welcome_df.instance.uid = peer.uid.bytes
        self.welcome_df.instance.pid = peer.pid
        self.welcome_df.instance.host = peer.host
        self.welcome_df.service.uid = service.agent.uid.bytes
        self.welcome_df.service.name = service.agent.name
        self.welcome_df.service.version = service.agent.version
        self.welcome_df.service.classification = service.agent.classification
        self.welcome_df.service.vendor.uid = service.agent.vendor_uid.bytes
        self.welcome_df.service.platform.uid = service.agent.platform_uid.bytes
        self.welcome_df.service.platform.version = service.agent.platform_version
        for i, _api in enumerate(self._apis):
            intf = self.welcome_df.api.add()
            intf.number = i
            intf.uid = _api.get_uid().bytes
    def accept_new_session(self, channel: Channel, routing_id: RoutingID, msg: FBSPMessage) -> bool:
        """Validates incoming message that initiated new session/transmission.

        Calls `on_accept_client` event handler that may reject the client by raising `.StopError`
        exception with appropriate error code to be sent to the client in ERROR message.

        Arguments:
            channel:    Channel that received the message.
            routing_id: Routing ID of the sender.
            msg:        Received message.
        """
        err_code = None
        err = None
        try:
            if msg.msg_type is not MsgType.HELLO:
                raise StopError("Expecting HELLO message", code=ErrorCode.PROTOCOL_VIOLATION)
            self.on_accept_client(channel, msg)
        except StopError as exc:
            err_code = getattr(exc, 'code', ErrorCode.ERROR)
        except Exception as exc:
            err_code = getattr(exc, 'code', ErrorCode.INTERNAL_ERROR)
            err = exc
        if err_code is not None:
            session = Session()
            session.routing_id = routing_id
            self.send_error(channel, session, msg, err_code, err)
            return False
        return True
    def register_api_handler(self, api_code: ButlerInterface, handler: Callable) -> None:
        """Register handler for REQUEST message for particular service API code.

        Arguments:
            api_code: API code.
            handler:  A callable that handles the API code matching the signature
                      (channel: Channel, session: FBSPSession, msg: APIMessage) -> None
        """
        # Validate handler via eventsocket
        _hndcheck.service_handler = handler
        _hndcheck.service_handler = None
        self.api_handlers[bb2h(self._apis.index(api_code.__class__), api_code.value)] = handler
    def create_welcome_reply(self, msg: HelloMessage) -> WelcomeMessage:
        """Create new `.WelcomeMessage` that is a reply to client's HELLO.

        Arguments:
            msg: `.HelloMessage` from the client
        """
        return self.create_message_for(MsgType.WELCOME, msg.token)
    def create_error_for(self, msg: FBSPMessage, error_code: ErrorCode) -> ErrorMessage:
        """Create new ErrorMessage that relates to specific message.

        Arguments:
            msg:        `FBSPMessage` instance that error relates to
            error_code: Error code
        """
        err = self.create_message_for(MsgType.ERROR, msg.token)
        err.relates_to = msg.msg_type
        err.error_code = error_code
        return err
    def create_reply_for(self, msg: APIMessage) -> APIMessage:
        """Create new ReplyMessage for specific RequestMessage.

        Arguments:
            msg: Request message instance that reply relates to
        """
        return self.create_message_for(MsgType.REPLY, msg.token, msg.type_data)
    def create_state_for(self, msg: APIMessage, state: State) -> StateMessage:
        """Create new `.StateMessage` that relates to specific `RequestMessage`.

        Arguments:
            msg:   Request message instance that state relates to
            state: State code
        """
        msg = self.create_message_for(MsgType.STATE, msg.token, msg.type_data)
        msg.state = state
        return msg
    def handle_exception(self, channel: Channel, session: Session, msg: Message, exc: Exception) -> None:
        """Called by `.handle_msg()` on exception in message handler.

        Sends `ERROR` message and then calls `.on_exception` handler.

        Important:
            The error code is extracted ONLY from `.StopError` exception. Other exception
            types will result in `6 - Internal Service Error` error code.

        Arguments:
            channel: Channel for communication with client
            session: Client session
            msg:     Message aasociated with exception
            exc:     Exception raised
        """
        error_code = getattr(exc, 'code', ErrorCode.ERROR) if isinstance(exc, StopError) \
            else ErrorCode.INTERNAL_ERROR
        self.send_error(channel, session, msg, error_code, exc)
        super().handle_exception(channel, session, msg, exc)
    def handle_unexpected_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process unexpected valid message received from client.

        Sends `ERROR` message to the client with error code `2 - Protocol violation`.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        raise StopError("Unexpected message", code=ErrorCode.PROTOCOL_VIOLATION)
    def handle_hello_msg(self, channel: Channel, session: FBSPSession, msg: HelloMessage) -> None:
        """Process `HELLO` message received from client.

        Sends `WELCOME` message to the client.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            The HELLO message was preprocessed and approved by `.accept_new_session()`.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
        session.greeting = msg
        session.partner_uid = uuid.UUID(bytes=msg.data.instance.uid)
        welcome = self.create_welcome_reply(msg)
        welcome.data.CopyFrom(self.welcome_df)
        channel.send(welcome, session)
    def handle_request_msg(self, channel: Channel, session: FBSPSession, msg: APIMessage) -> None:
        """Process `REQUEST` message received from client.

        Calls the appropriate API handler set via `.register_api_handler()`.

        Important:
            The registered API handler is responsible for sending the `ACK-REPLY`
            message if the incoming request `msg` has the `ACK_REQ` flag set.
            According to FBSP specification, the request should be acknowledged
            once the Service has decided to accept it and before starting fulfillment.
            The handler may also send an `ERROR` message instead of an `ACK-REPLY`.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
        handler = self.api_handlers.get(msg.type_data)
        if handler is None:
            raise StopError("", code=ErrorCode.NOT_IMPLEMENTED)
        handler(channel, session, msg, self)
    def handle_cancel_msg(self, channel: Channel, session: FBSPSession, msg: CancelMessage) -> None:
        """Process `CANCEL` message received from peer.

        Calls `on_cancel` event handler. According to FBSP, the service must send the ERROR
        message with appropriate error code (if request was successfuly cancelled, the code
        must be `17 - Request Cancelled`). To follow the common pattern, the event handler
        must raise an `.StopError` exception with `code attribute` set to the error code
        to be returned in ERROR message.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Raises:
            StopError: With error code `4 - Not Implemented` if event handler is not defined.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
        self.on_cancel(channel, session, msg)
        if not self.on_cancel.is_set():
            raise StopError("Request cancellation not supported", code=ErrorCode.NOT_IMPLEMENTED)
    def handle_noop_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process `NOOP` message received from client.

        If message is an ACK-REPLY, it calls `on_ack_received` event handler.
        Otherwise it sends ACK-REPLY if requested and then calls `on_noop` event handler.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
        if msg.has_ack_reply():
            self.on_ack_received(channel, session, msg)
            return
        if msg.has_ack_req():
            channel.send(self.create_ack_reply(msg), session)
        self.on_noop(channel, session)
    def handle_data_msg(self, channel: Channel, session: FBSPSession, msg: DataMessage) -> None:
        """Process `DATA` message received from peer.

        If message is an ACK-REPLY, it calls `on_ack_received` event handler. Otherwise it
        calls `on_data` event handler (that must also handle the ACK-REQ if set).

        If `on_data` event handler is not defined, the handler sends ERROR message
        with code `2 - Protocol violation` by raising the `.StopError`.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
        if msg.has_ack_reply():
            self.on_ack_received(channel, session, msg)
            return
        self.on_data(channel, session, msg)
        if not self.on_data.is_set():
            raise StopError("Unexpected DATA message", code=ErrorCode.PROTOCOL_VIOLATION)
    def handle_close_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process `CLOSE` message received from client.

        Calls `on_session_closed` event handler and then discards the session.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Important:
            All exceptions raised by event handler are silently ignored.
        """
        try:
            self.on_session_closed(channel, session, msg)
        except Exception:
            # We don't want to handle this via `handle_exception` and we're closing
            # the session anyway
            pass
        finally:
            channel.discard_session(session)
    def handle_ack_reply(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process ACK-REPLY messages received from client.

        If message has ACK-REPLY flag set, it calls `on_ack_received` event handler.
        Otherwise it raises `.StopError` with PROTOCOL_VIOLATION error code.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
        if msg.has_ack_reply():
            self.on_ack_received(channel, session, msg)
        else:
            raise StopError(f"Client can send {msg.msg_type.name} messages only as ACK-REPLY",
                            code=ErrorCode.PROTOCOL_VIOLATION)
    def send_error(self, channel: Channel, session: FBSPSession, relates_to: FBSPMessage,
                   error_code: ErrorCode, exc: Exception | None=None) -> None:
        """Sends `ERROR` message to the client associated with session.

        Arguments:
            channel: Channel associate with data pipe.
            session: Session associated with transmission.
            relates_to: FBSP message to which this ERROR is related.
            error_code: Error code.
            exc: Exception that caused the error.
        """
        msg: ErrorMessage = self.create_message_for(MsgType.ERROR, relates_to.token)
        msg.error_code = error_code
        msg.relates_to = relates_to.msg_type
        if exc is not None:
            msg.note_exception(exc)
        channel.send(msg, session)
    def send_close(self, channel: Channel, session: FBSPSession) -> None:
        """Sends `CLOSE` message to the client associated with session and calls
        `on_session_closed` event handler. The message passed to the event handler is
        the initial `HELLO` message from client.

        Arguments:
            channel: Channel associate with data pipe.
            session: Session associated with transmission.

        Important:
            All exceptions raised by event handler are silently ignored.
        """
        channel.send(self.create_message_for(MsgType.CLOSE, session.greeting.token), session)
        with suppress(Exception):
            # We don't want to handle exception via `handle_exception` and we're closing
            # the session anyway
            self.on_session_closed(channel, session, session.greeting)
    def close(self, channel: Channel):
        """Close all connections to attached clients.

        Arguments:
          channel: Channel used for transmission
        """
        while channel.sessions:
            _, session = channel.sessions.popitem()
            with suppress(Exception):
                # channel could be already closed from other side, as we are closing it too
                # we can ignore any send errors
                self.send_close(channel, session)
    @eventsocket
    def on_accept_client(self, channel: Channel, msg: HelloMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when HELLO message is received from
        client.

        Arguments:
            channel: Channel that received the message.
            msg:     Received message.

        The event handler may reject the client by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in ERROR message.

        If event handler does not raise an exception, the client is accepted, new session
        is created and WELCOME message is sent to the client.
        """
    @eventsocket
    def on_cancel(self, channel: Channel, session: FBSPSession, msg: CancelMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when CANCEL message is received from
        client.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        The event handler must raise an `.Error` exception with `code` attribute set to
        the error code to be returned in ERROR message. If request was successfuly cancelled,
        the code must be `ErrorCode.REQUEST_CANCELLED`.
        """
    @eventsocket
    def on_noop(self, channel: Channel, session: FBSPSession) -> None:
        """`~firebird.base.signal.eventsocket` called when NOOP message is received, and
        after ACK-REPLY (if requested) is send.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
    @eventsocket
    def on_data(self, channel: Channel, session: FBSPSession, msg: DataMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when DATA message is received.

        Important:
            If handler is defined, it must send the ACK-REPLY if received message has
            ACK-REQ set. It's up to service interface whether ACK-REPLY would be sent
            before, or after data contained within message are processed.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
    @eventsocket
    def on_session_closed(self, channel: Channel, session: FBSPSession, msg: FBSPMessage,
                          exc: Exception | None=None) -> None:
        """`~firebird.base.signal.eventsocket` called when CLOSE message is received or
        sent, to release any resources associated with current transmission.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            msg: Received/sent CLOSE message.
            exc: Exception that caused the error.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
    @eventsocket
    def on_ack_received(self, channel: Channel, session: FBSPSession, msg: DataMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when ACK-REPLY NOOP, DATA, REPLY or
        STATE message is received.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received ACK-REPLY message.

        Note:
            All exceptions raised by handler are handled by `handle_exception`.
        """

class FBSPClient(_FBSP):
    """4/FBSP - Firebird Butler Service Protocol - Client side.

    This is the RAW version of client side FBSP protocol for clients that directly process
    FBSP messages received from service. Such clients call `Channel.receive()` and then
    process the returned message or sentinel.

    This protocol implementation handles only essential message processing:

    - Message parsing.
    - ACK-REQ for received STATE and NOOP messages.
    - Returns INVALID sentinel for received HELLO and CANCEL messages.
    - Closes the session when CLOSE message is received.
    """
    def __init__(self, *, session_type: type[FBSPSession]=FBSPSession):
        """
        Arguments:
            session_type: Class for session objects.
        """
        super().__init__(session_type=session_type)
        self.handlers.update({MsgType.WELCOME: self.handle_welcome_msg,
                              MsgType.ERROR: self.handle_fbsp_msg,
                              MsgType.REPLY: self.handle_fbsp_msg,
                              MsgType.STATE: self.handle_fbsp_msg,
                              MsgType.NOOP: self.handle_noop_msg,
                              MsgType.DATA: self.handle_fbsp_msg,
                              MsgType.CLOSE: self.handle_close_msg,
                              MsgType.REQUEST: self.handle_fbsp_msg,
                              MsgType.HELLO: self.handle_unexpected_msg,
                              MsgType.CANCEL: self.handle_unexpected_msg,
                              })
        self._apis: dict[ButlerInterface, int] = {}
    def handle_welcome_msg(self, channel: Channel, session: FBSPSession, msg: WelcomeMessage) -> WelcomeMessage:
        """Process `WELCOME` message received from service.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        session.greeting = msg
        session.partner_uid = uuid.UUID(bytes=msg.data.service.uid)
        for intf in msg.data.api:
            self._apis[uuid.UUID(bytes=intf.uid)] = intf.number
        return msg
    def handle_fbsp_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> FBSPMessage:
        """FBSP message handler that simply returns received message.

        If message is a `STATE` message with ACK-REQ, sends ACK-REPLY. ACK-REQ for other
        messages must be handled by caller.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions raised in handler are handled by `handle_exception`.
        """
        if (msg.msg_type is MsgType.STATE) and msg.has_ack_req():
            channel.send(self.create_ack_reply(msg), session)
        return msg
    def handle_unexpected_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> FBSPMessage:
        """FBSP message handler that returns INVALID sentinel.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        return INVALID
    def handle_noop_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process `NOOP` message received from service.

        Sends ACK-REPLY if requested.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        if msg.has_ack_req():
            channel.send(self.create_ack_reply(msg), session)
    def handle_close_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> FBSPMessage:
        """Process `CLOSE` message received from service.

        Discards the session and returns the CLOSE message received.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        channel.discard_session(session)
        return msg
    def has_api(self, api: type[ButlerInterface]) -> bool:
        """Returns True if attached service supports specified interface.

        Arguments:
            api: Service API (interface) enumeration.
        """
        return api.get_uid() in self._apis
    def create_request_for(self, session: FBSPSession, api_code: ButlerInterface, token: Token) -> APIMessage:
        """Returns new `REQUEST` message for specific API call.

        Arguments:
          session:  Session instance
          api_code: API Code
          token:    Message token
        """
        return self.create_message_for(MsgType.REQUEST, token,
                                       bb2h(self._apis[api_code.__class__.get_uid()],
                                            api_code.value))
    def exception_for(self, msg: ErrorMessage) -> ServiceError:
        """Returns a .ServiceError exception populated with details from the provided ERROR
        message.

        Arguments:
          msg: ERROR message received
        """
        desc = [f"{msg.error_code.name}, relates to {msg.relates_to.name}"]
        for err in msg.errors:
            desc.append(f"#{err.code} : {err.description}")
        return ServiceError('\n'.join(desc))
    def send_hello(self, channel: Channel, session: FBSPSession, agent: AgentDescriptor,
                   peer: PeerDescriptor, token: Token=bytes(8)) -> None:
        """Sends `HELLO` message to the service.

        Arguments:
            channel: Channel used for connection to the service.
            session: Session associated with service.
            agent: Agent descriptor for client.
            peer: Peer descriptor for client.
            token: FBSP message token to be used in HELLO message.
        """
        msg: HelloMessage = self.create_message_for(MsgType.HELLO, token)
        msg.data.instance.uid = peer.uid.bytes
        msg.data.instance.pid = peer.pid
        msg.data.instance.host = peer.host
        msg.data.client.uid = agent.uid.bytes
        msg.data.client.name = agent.name
        msg.data.client.version = agent.version
        msg.data.client.classification = agent.classification
        msg.data.client.vendor.uid = agent.vendor_uid.bytes
        msg.data.client.platform.uid = agent.platform_uid.bytes
        msg.data.client.platform.version = agent.platform_version
        channel.send(msg, session)
    def send_close(self, channel: Channel, session: FBSPSession) -> None:
        """Sends `CLOSE` message to the service associated with session.

        Arguments:
            channel: Channel associate with data pipe.
            session: Session associated with transmission.
        """
        channel.send(self.create_message_for(MsgType.CLOSE, session.greeting.token), session)

class FBSPEventClient(FBSPClient):
    """4/FBSP - Firebird Butler Service Protocol - Client side.

    This is the EVENT version of client side FBSP protocol for clients that process
    FBSP messages received from service indirectly. Such clients use central I/O loop
    that process incomming messages in uniform way, and actual processing is done via event
    handlers.
    """
    def __init__(self, *, session_type: type[FBSPSession]=FBSPSession):
        """
        Arguments:
            session_type: Class for session objects.
        """
        super().__init__(session_type=session_type)
        self.api_handlers: dict[Any, Callable] = {}
        self.handlers.update({MsgType.WELCOME: self.handle_welcome_msg,
                              MsgType.ERROR: self.handle_error_msg,
                              MsgType.REPLY: self.handle_reply_msg,
                              MsgType.STATE: self.handle_state_msg,
                              MsgType.NOOP: self.handle_noop_msg,
                              MsgType.DATA: self.handle_data_msg,
                              MsgType.CLOSE: self.handle_close_msg,
                              MsgType.REQUEST: self.handle_ack_reply,
                              MsgType.HELLO: self.handle_unexpected_msg,
                              MsgType.CANCEL: self.handle_unexpected_msg,
                              })
    def register_api_handler(self, api_code: ButlerInterface, handler: Callable) -> None:
        """Register handler for response messages for particular service API code.

        Arguments:
            api_code: API code.
            handler:  Callable that handles the API code matching the signature
                      (channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None.
        """
        # Validate handler via eventsocket
        _hndcheck.client_handler = handler
        _hndcheck.client_handler = None
        self.api_handlers[bb2h(self._apis[api_code.__class__.get_uid()], api_code.value)] = handler
    def handle_unexpected_msg(self, channel: Channel, session: FBSPSession, msg: HelloMessage) -> None:
        """Process unexpected valid message received from service.

        Raises `.StopError` with error code `2 - Protocol violation`.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        raise StopError("Unexpected message", code=ErrorCode.PROTOCOL_VIOLATION)
    def handle_welcome_msg(self, channel: Channel, session: FBSPSession, msg: WelcomeMessage) -> None:
        """Process `WELCOME` message received from service.

        Calls `on_service_connected` event handler.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        super().handle_welcome_msg(channel, session, msg)
        self.on_service_connected(channel, session, msg, self)
    def handle_error_msg(self, channel: Channel, session: FBSPSession, msg: ErrorMessage) -> None:
        """Process `ERROR` message received from service.

        Calls `.on_error` event handler.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        self.on_error(channel, session, msg)
    def handle_reply_msg(self, channel: Channel, session: FBSPSession, msg: APIMessage) -> None:
        """Process `REPLY` message received from service.

        Calls the appropriate API handler set via `.register_api_handler()`.

        Important:
            The registered API handler must send the `ACK-REPLY` message if requested.
            According to FBSP specification, the reply must be acknowledged without any delay,
            unless a previous agreement between the Client and the Service exists to handle
            it differently (for example when Client is prepared to accept subsequent `DATA` or
            other messages from Service).

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        handler = self.api_handlers.get(msg.type_data)
        handler(channel, session, msg, self)
    def handle_state_msg(self, channel: Channel, session: FBSPSession, msg: StateMessage) -> None:
        """Process `STATE` message received from service.

        Sends ACK-REPLY if requested and calls `.on_state` event handler.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        if msg.has_ack_req():
            channel.send(self.create_ack_reply(msg), session)
        self.on_state(channel, session, msg)
    def handle_noop_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process `NOOP` message received from service.

        If message is an ACK-REPLY, it calls `.on_ack_received` event handler.
        Otherwise it sends ACK-REPLY if requested and then calls `.on_noop` event handler.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        if msg.has_ack_reply():
            self.on_ack_received(channel, session, msg)
            return
        if msg.has_ack_req():
            channel.send(self.create_ack_reply(msg), session)
        self.on_noop(channel, session)
    def handle_data_msg(self, channel: Channel, session: FBSPSession, msg: DataMessage) -> None:
        """Process `DATA` message received from serviec.

        If message is an ACK-REPLY, it calls `.on_ack_received` event handler.
        Otherwise it calls `.on_data` event handler that must handle the ACK-REQ if set.
        If `.on_data` event handler is not defined, the ACK-REPLY message is send by this
        handler.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        if msg.has_ack_reply():
            self.on_ack_received(channel, session, msg)
            return
        self.on_data(channel, session, msg)
        if not self.on_data.is_set() and msg.has_ack_req():
            channel.send(self.create_ack_reply(msg), session)
    def handle_close_msg(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process `CLOSE` message received from service.

        Calls `.on_session_closed` event handler and then discards the session.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        try:
            self.on_session_closed(channel, session, msg)
        except Exception:
            # We don't want to handle this via `handle_exception` and we're closing
            # the session anyway
            pass
        finally:
            channel.discard_session(session)
    def handle_ack_reply(self, channel: Channel, session: FBSPSession, msg: FBSPMessage) -> None:
        """Process ACK-REPLY messages received from service.

        If message has ACK-REPLY flag set, it calls `.on_ack_received` event handler.
        Otherwise it's ignored because it violates the protocol.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
        if msg.has_ack_reply():
            self.on_ack_received(channel, session, msg)
    @eventsocket
    def on_service_connected(self, channel: Channel, session: FBSPSession,
                             msg: WelcomeMessage, protocol: FBSPEventClient) -> None:
        """`~firebird.base.signal.eventsocket` called when `WELCOME` message is received
        from service.

        Arguments:
            channel:  Channel that received the message.
            session:  Session instance.
            msg:      Received message.
            protocol: This FBSPEventClient instance, passed to allow the handler to make
                      further protocol calls if needed.

        The event handler should register all service API handlers for `REPLY` messages
        (see `FBSPEventClient.register_api_handler()`).
        """

    @eventsocket
    def on_noop(self, channel: Channel, session: FBSPSession) -> None:
        """`~firebird.base.signal.eventsocket` called when `NOOP` message is received, and
        after ACK-REPLY (if requested) is send.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
        """
    @eventsocket
    def on_data(self, channel: Channel, session: FBSPSession, msg: DataMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when `DATA` message is received.

        Important:
            If handler is defined, it must send the ACK-REPLY if received message has
            ACK-REQ set. It's up to service interface whether ACK-REPLY would be sent
            before, or after data contained within message are processed.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
    @eventsocket
    def on_error(self, channel: Channel, session: FBSPSession, msg: ErrorMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when `ERROR` message is received.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
    @eventsocket
    def on_state(self, channel: Channel, session: FBSPSession, msg: StateMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when `STATE` message is received.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """
    @eventsocket
    def on_session_closed(self, channel: Channel, session: FBSPSession, msg: FBSPMessage,
                          exc: Exception | None=None) -> None:
        """`~firebird.base.signal.eventsocket` called when `CLOSE` message is received or
        sent, to release any resources associated with current transmission.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            msg: Received/sent CLOSE message.
            exc: Exception that caused the error.
        """
    @eventsocket
    def on_ack_received(self, channel: Channel, session: FBSPSession, msg: DataMessage) -> None:
        """`~firebird.base.signal.eventsocket` called when ACK-REPLY message is received.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received ACK-REPLY message.

        Note:
            All exceptions are handled by `~saturnin.base.transport.Protocol.handle_exception`.
        """

class _APIHandlerChecker:
    """Helper class for validation of API handlers.
    """
    @eventsocket
    def service_handler(self, channel: Channel, session: FBSPSession, msg: FBSPMessage,
                        protocol: FBSPService) -> None:
        "Signature definition for FBSP Service API handlers."
    @eventsocket
    def client_handler(self, channel: Channel, session: FBSPSession, msg: FBSPMessage,
                       protocol: FBSPEventClient) -> None:
        "Signature definition for FBSP Event Client API handlers."

_hndcheck: _APIHandlerChecker = _APIHandlerChecker()
