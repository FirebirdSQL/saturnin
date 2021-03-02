#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/protocol/fbdp.py
# DESCRIPTION:    Firebird Butler Data Pipe Protocol
#                 See https://firebird-butler.readthedocs.io/en/latest/rfc/9/FBDP.html
# CREATED:        30.7.2019
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

"""Saturnin reference implementation of Firebird Butler Data Pipe Protocol

See https://firebird-butler.readthedocs.io/en/latest/rfc/9/FBDP.html
"""

from __future__ import annotations
from typing import Type, Dict, Any, Union
import uuid
import warnings
from struct import pack, unpack
from enum import IntEnum, IntFlag
from firebird.base.signal import eventsocket
from firebird.base.protobuf import ProtoMessage, create_message, dict2struct, struct2dict
from saturnin.base import InvalidMessageError, StopError, RoutingID, TZMQMessage, \
     PipeSocket, Channel, Protocol, Message, Session, ANY

PROTO_OPEN = 'firebird.butler.FBDPOpenDataframe'
PROTO_ERROR = 'firebird.butler.ErrorDescription'

#: FBDP protocol control frame :mod:`struct` format
HEADER_FMT_FULL : str = '!4sBBH'
#: FBDP protocol control frame :mod:`struct` format without FOURCC
HEADER_FMT: str = '!4xBBH'
#: FBDP protocol identification (FOURCC)
FOURCC: bytes = b'FBDP'
#: FBDP protocol version mask
VERSION_MASK: int = 7

#: Default data batch size
DATA_BATCH_SIZE: int = 50

class MsgType(IntEnum):
    """FBDP Message Type"""
    UNKNOWN = 0 # not a valid message type
    OPEN = 1    # initial message from client
    READY = 2   # transfer negotiation message
    NOOP = 3    # no operation, used for keep-alive & ping purposes
    DATA = 4    # user data
    CLOSE = 5   # sent by peer that is going to close the connection

class MsgFlag(IntFlag):
    """FBDP message flag"""
    NONE = 0
    ACK_REQ = 1
    ACK_REPLY = 2

class ErrorCode(IntEnum):
    """FBDP Error Code"""
    # No error
    OK = 0
    # General errors
    INVALID_MESSAGE = 1
    PROTOCOL_VIOLATION = 2
    ERROR = 3
    INTERNAL_ERROR = 4
    INVALID_DATA = 5
    TIMEOUT = 6
    # Errors that prevent the connection from opening
    PIPE_ENDPOINT_UNAVAILABLE = 100
    FBDP_VERSION_NOT_SUPPORTED = 101
    NOT_IMPLEMENTED = 102
    DATA_FORMAT_NOT_SUPPORTED = 103


class FBDPMessage(Message):
    """Firebird Butler Datapipe Protocol (FBDP) Message.
    """
    def __init__(self):
        #: Type of message
        self.msg_type: MsgType = MsgType.UNKNOWN
        #: Message flags
        self.flags: MsgFlag = MsgFlag(0)
        #: Data associated with message
        self.type_data: int = 0
        #: Data frame associated with message type (or None)
        self.data_frame: Union[ProtoMessage, Any] = None
    def __str__(self):
        return f"{self.__class__.__qualname__}[{self.msg_type.name}]"
    __repr__ = __str__
    def from_zmsg(self, zmsg: TZMQMessage) -> None:
        """Populate message data from sequence of ZMQ data frames.

        Arguments:
            zmsg: Sequence of frames that should be deserialized.

        Raises:
            InvalidMessageError: If message is not a valid protocol message.
        """
        try:
            control_byte, flags, self.type_data = unpack(HEADER_FMT, zmsg.pop(0))
            self.msg_type = MsgType(control_byte >> 3)
            self.flags = MsgFlag(flags)
            if self.msg_type is MsgType.OPEN:
                self.data_frame = create_message(PROTO_OPEN)
                self.data_frame.ParseFromString(zmsg.pop(0))
            elif self.msg_type is MsgType.DATA:
                self.data_frame = zmsg.pop(0) if zmsg else None
            elif self.msg_type is MsgType.CLOSE:
                self.type_data = ErrorCode(self.type_data)
                self.data_frame = []
                while zmsg:
                    err = create_message(PROTO_ERROR)
                    err.ParseFromString(zmsg.pop(0))
                    self.data_frame.append(err)
        except Exception as exc:
            raise InvalidMessageError("Invalid message") from exc
    def as_zmsg(self) -> TZMQMessage:
        """Returns message as sequence of ZMQ data frames.
        """
        zmsg = []
        zmsg.append(self.get_header())
        if self.msg_type is MsgType.OPEN:
            zmsg.append(self.data_frame.SerializeToString())
        elif (self.msg_type is MsgType.DATA and self.data_frame is not None):
            zmsg.append(self.data_frame)
        elif self.msg_type is MsgType.CLOSE:
            while self.data_frame:
                zmsg.append(self.data_frame.pop(0).SerializeToString())
        return zmsg
    def clear(self) -> None:
        """Clears message data.
        """
        self.msg_type = MsgType.UNKNOWN
        self.type_data = 0
        self.flags = MsgFlag(0)
        self.data_frame = None
    def copy(self) -> Message:
        """Returns copy of the message.
        """
        msg: FBDPMessage = self.__class__()
        msg.msg_type = self.msg_type
        msg.flags = self.flags
        msg.type_data = self.type_data
        if self.msg_type is MsgType.OPEN:
            msg.data_frame = create_message(PROTO_OPEN)
            msg.data_frame.CopyFrom(self.data_frame)
        elif self.msg_type is MsgType.CLOSE:
            msg.data_frame = []
            for frame in self.data_frame:
                err = create_message(PROTO_ERROR)
                err.CopyFrom(frame)
                msg.data_frame.append(err)
        else:
            msg.data_frame = self.data_frame
        return msg
    def get_keys(self) -> Iterable:
        """Returns iterable of dictionary keys to be used with `Protocol.handlers`.
        Keys must be provided in order of precedence (from more specific to general).
        """
        return [self.msg_type, ANY]
    def get_header(self) -> bytes:
        """Return message header (FBDP control frame).
        """
        return pack(HEADER_FMT_FULL, FOURCC, (self.msg_type << 3) | _FBDP.REVISION,
                    self.flags, self.type_data)
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
    def note_exception(self, exc: Exception):
        """Store information from exception into CLOSE Message.
        """
        assert self.msg_type is MsgType.CLOSE
        errdesc = create_message(PROTO_ERROR)
        if hasattr(exc, 'code'):
            errdesc.code = getattr(exc, 'code')
        errdesc.description = str(exc)
        self.data_frame.append(errdesc)

class FBDPSession(Session):
    """FBDP session. Contains information about Data Pipe.
    """
    def __init__(self):
        super().__init__()
        #: Data Pipe Identification.
        self.pipe: str = None
        #: Data Pipe socket Identification.
        self.socket: PipeSocket = None
        #: Specification of format for user data transmitted in DATA messages.
        self.data_format: str = None
        #: Data Pipe parameters.
        self.params: Dict = {}
        #: Number of DATA messages that remain to be transmitted since last READY message.
        self.transmit: int = None
        #: Indicator that server sent READY and waits from READY response from client
        self.await_ready: bool = False

class _FBDP(Protocol):
    """9/FBDP - Firebird Butler Data Pipe Protocol
    """
    #: string with protocol OID (dot notation).
    OID: str =  '1.3.6.1.4.1.53446.1.5.2'
    # iso.org.dod.internet.private.enterprise.firebird.butler.protocol.fbdp
    #: UUID instance that identifies the protocol.
    UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, OID)
    def __init__(self, *, session_type: Type[FBDPSession] = FBDPSession):
        """
        Arguments:
            session_type: Class for session objects.
            batch_size: Default batch size.
        """
        super().__init__(session_type=session_type)
        #: Initial batch size
        self.batch_size = DATA_BATCH_SIZE
        #: CONSUMER option. Whether ACK_REPLY message for DATA/ACK_REQ should be sent
        #: before (False) or after (True) call to `.on_accept_data()` callback.
        self.confirm_processing: bool = False
        #: PRODUCER option. If sent DATA message has ACK_REQ flag set, send next DATA
        #: message after ACK_REPLY is received (True), or continue sending DATA without
        #: delay (False).
        self.send_after_confirmed: bool = True
        # Session socket that means that messages flow to us
        self._flow_in_socket: PipeSocket = None
        self.on_produce_data = self.handle_produce_data
        self.on_accept_data = self.handle_accept_data
        self._msg: FBDPMessage = FBDPMessage()
        self.message_factory = self.__message_factory
        self.handlers.update({MsgType.NOOP: self.handle_noop_msg,
                              MsgType.DATA: self.handle_data_msg,
                              MsgType.CLOSE: self.handle_close_msg,
                              })
    def __message_factory(self, zmsg: TZMQMessage=None) -> Message:
        "Internal message factory"
        self._msg.clear()
        return self._msg
    def _init_new_batch(self, channel: Channel, session: FBDPSession) -> None:
        """Initializes the transmission of a new batch of DATA messages.
        """
        raise NotImplementedError()
    def _send_data(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Sends next DATA message to the client attached to PIPE_OUTPUT.
        """
        error_code = None
        exc = None
        try:
            self.on_produce_data(channel, session, msg)
            channel.send(msg, session)
            session.transmit -= 1
            if session.transmit > 0:
                if msg.has_ack_req() and self.send_after_confirmed:
                    channel.set_wait_out(False, session)
                elif self.on_get_data.is_set():
                    if not self.on_get_data(channel, session):
                        channel.set_wait_out(False, session)
            else:
                channel.set_wait_out(False, session)
                self._init_new_batch(channel, session)
        except StopError as err:
            error_code = getattr(err, 'code', ErrorCode.ERROR)
            if error_code is not ErrorCode.OK:
                exc = err
        except Exception as err:
            error_code = ErrorCode.INTERNAL_ERROR
            exc = err
        if error_code is not None:
            self.send_close(channel, session, error_code, exc)
    def _on_output_ready(self, channel: Channel) -> None:
        """Event handler called when channel is ready to accept at least one outgoing message
        without blocking (or dropping it).
        """
        for session in list(channel.sessions.values()):
            if session.send_pending:
                msg = self.create_message_for(MsgType.DATA)
                # This is called directly and not via `handle_msg()` and message handler,
                # so it's necessary to handle exceptions like `handle_msg()` does.
                try:
                    self._send_data(channel, session, msg)
                except Exception as exc:
                    try:
                        self.handle_exception(channel, session, msg, exc)
                    except:
                        warnings.warn('Exception raised in exception handler', RuntimeWarning)
    def validate(self, zmsg: TZMQMessage) -> None:
        """Verifies that sequence of ZMQ data frames is a valid protocol message.

        If this validation passes without exception, then `.parse()` of the same message
        must be successful as well.

        Arguments:
            zmsg:   ZeroMQ multipart message.

        Raises:
            InvalidMessageError: If ZMQ message is not a valid protocol message.
        """
        if not zmsg:
            raise InvalidMessageError("Empty message")
        fbdp_header = zmsg[0]
        if len(fbdp_header) != 8:
            raise InvalidMessageError("Message header must be 8 bytes long")
        try:
            fourcc, control_byte, flags, _ = unpack(HEADER_FMT_FULL, fbdp_header)
        except Exception as exp:
            raise InvalidMessageError("Invalid control frame") from exp
        if fourcc != FOURCC:
            raise InvalidMessageError("Invalid FourCC")
        if (control_byte & VERSION_MASK) != self.REVISION:
            raise InvalidMessageError("Invalid protocol version")
        if (flags | 3) > 3:
            raise InvalidMessageError("Invalid flags")
        try:
            message_type = MsgType(control_byte >> 3)
        except ValueError:
            raise InvalidMessageError(f"Illegal message type {control_byte >> 3}")
        if message_type is MsgType.OPEN:
            if len(zmsg) != 2:
                raise InvalidMessageError("OPEN message must have a dataframe")
            try:
                fpb = create_message(PROTO_OPEN)
                fpb.ParseFromString(zmsg[1])
                if not fpb.data_pipe:
                    raise ValueError("Missing 'data_pipe' specification")
                pipe_socket = PipeSocket(fpb.pipe_socket)
                if pipe_socket is PipeSocket.UNKNOWN_PIPE_SOCKET:
                    raise ValueError("Invalid 'pipe_socket'")
                if not fpb.data_format:
                    raise ValueError("Missing 'data_format' specification")
            except Exception as exc:
                raise InvalidMessageError("Invalid data frame for OPEN message") from exc
        elif (message_type is MsgType.CLOSE and len(zmsg) > 1):
            fpb = create_message(PROTO_ERROR)
            for frame in zmsg[1:]:
                fpb.ParseFromString(frame)
                if not fpb.description:
                    raise InvalidMessageError("Missing error description")
        elif (message_type is MsgType.DATA and len(zmsg) > 2):
            raise InvalidMessageError("DATA message may have only one data frame")
        elif (message_type in (MsgType.READY, MsgType.NOOP) and len(zmsg) > 1):
            raise InvalidMessageError("Data frames not allowed for READY and NOOP messages")
    def handle_exception(self, channel: Channel, session: Session, msg: Message, exc: Exception) -> None:
        """Called by `.handle_msg()` on exception in message handler.

        Sends CLOSE message and calls `on_exception` handler.
        """
        error_code = getattr(exc, 'code', ErrorCode.ERROR) if isinstance(exc, StopError) \
            else ErrorCode.INTERNAL_ERROR
        self.send_close(channel, session, error_code, exc)
        super().handle_exception(channel, session, msg, exc)
    def handle_produce_data(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Default event handler executed when DATA message should be sent to pipe.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            msg: DATA message that will be sent to peer.

        Important:
            The base implementation simply raises StopError with ErrorCode.OK code,
            which closes the pipe normally.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_accept_data(self, channel: Channel, session: FBDPSession, data: bytes) -> None:
        """Default event hander executed when DATA message is received from pipe.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            data: Data received from peer.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.

        Note:
            The ACK-REQUEST in received DATA message is handled automatically by protocol.

        Important:
            The base implementation simply raises StopError with ErrorCode.OK code,
            which closes the pipe normally.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_noop_msg(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Process NOOP message received from peer.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        if msg.has_ack_req():
            channel.send(self.create_ack_reply(msg), session)
        self.on_noop(channel, session)
    def handle_data_msg(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Process DATA message received from client.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `handle_exception`.
        """
        if session.socket is self._flow_in_socket:
            # DATA flow to us (INPUT for server context, OUTPUT for client context)
            if session.transmit is None:
                # Transmission not started, DATA out of band
                raise StopError("Out of band DATA message",
                                code=ErrorCode.PROTOCOL_VIOLATION)
            # ACK before processing?
            if msg.has_ack_req() and not self.confirm_processing:
                # We must create reply message directly to keep received message
                reply = FBDPMessage()
                reply.msg_type = msg.msg_type
                reply.type_data = msg.type_data
                reply.set_flag(MsgFlag.ACK_REPLY)
                if channel.send(msg, session) != 0:
                    raise StopError("ACK-REPLY send failed", code=ErrorCode.ERROR)
            # Process incoming data
            self.on_accept_data(channel, session, msg.data_frame)
            # ACK after processing?
            if msg.has_ack_req() and self.confirm_processing:
                if channel.send(self.create_ack_reply(msg), session) != 0:
                    raise StopError("ACK-REPLY send failed", code=ErrorCode.ERROR)
            session.transmit -= 1
            if session.transmit == 0:
                self._init_new_batch(channel, session)
        else:
            # DATA flow from us (OUTPUT for server context, INPUT for client context)
            if msg.has_ack_reply():
                if (session.transmit > 0) and self.send_after_confirmed:
                    # Re-Initiate transfer to output (via I/O loop) if data are available
                    if not self.on_get_data.is_set() or self.on_get_data(channel, session):
                        channel.set_wait_out(True, session)
                self.on_data_confirmed(channel, session, msg.type_data)
            else:
                # Only client attached to PIPE_INPUT can send DATA messages
                socket: PipeSocket = PipeSocket.OUTPUT \
                    if self._flow_in_socket is PipeSocket.INPUT else PipeSocket.INPUT
                raise StopError(f"DATA message sent to {socket.name} socket",
                                code=ErrorCode.PROTOCOL_VIOLATION)
    def handle_close_msg(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Process CLOSE message received from client.

        Calls `on_pipe_closed` and then discards the session.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.
        """
        try:
            self.on_pipe_closed(channel, session, msg)
        except:
            # We don't want to handle this via `handle_exception` and we're closing
            # the pipe anyway
            pass
        finally:
            channel.discard_session(session)
    def create_message_for(self, msg_type: MsgType, type_data: int=0, flags: MsgFlag=None) -> FBDPMessage:
        """Returns message of particular FBDP message type.

        Arguments:
            msg_type:  Type of message to be created.
            type_data: Message control data.
            flags:     Message flags.
        """
        msg: FBDPMessage = self.message_factory()
        msg.msg_type = msg_type
        msg.type_data = type_data
        if flags is not None:
            msg.flags = flags
        if msg.msg_type is MsgType.OPEN:
            msg.data_frame = create_message(PROTO_OPEN)
        elif msg.msg_type is MsgType.CLOSE:
            msg.data_frame = []
        return msg
    def create_ack_reply(self, msg: FBDPMessage) -> FBDPMessage:
        """Returns new message that is an ACK-REPLY response message.

        Arguments:
            msg: Message to be answered.
        """
        reply = self.create_message_for(msg.msg_type, msg.type_data, msg.flags)
        reply.clear_flag(MsgFlag.ACK_REQ)
        reply.set_flag(MsgFlag.ACK_REPLY)
        return reply
    def send_ready(self, channel: Channel, session: FBDPSession, batch_size: int) -> None:
        """Sends `READY` message.

        Arguments:
            channel: Channel associate with data pipe.
            session: Session associated with transmission.
            batch_size: Requested data transmission batch size.

        Raises:
            StopError: When sending message fails.
        """
        msg = self.create_message_for(MsgType.READY, batch_size)
        if channel.send(msg, session) != 0:
            raise StopError("Broken pipe, can't send READY message", code=ErrorCode.ERROR)
    def send_close(self, channel: Channel, session: FBDPSession, error_code: ErrorCode,
                   exc: Exception=None) -> None:
        """Sends `CLOSE` message, calls `on_pipe_closed` and then discards the session.

        Arguments:
            channel: Channel associate with data pipe.
            session: Session associated with transmission.
            error_code: Error code.
            exc: Exception that caused the error.
        """
        msg = self.create_message_for(MsgType.CLOSE, error_code)
        if exc:
            msg.note_exception(exc)
        try:
            channel.send(msg, session)
            self.on_pipe_closed(channel, session, msg, exc)
        finally:
            channel.discard_session(session)
    @eventsocket
    def on_pipe_closed(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                       exc: Exception=None) -> None:
        """Called when CLOSE message is received or sent, to release any resources
        associated with current transmission.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            msg: Received/sent CLOSE message.
            exc: Exception that caused the error.
        """
    @eventsocket
    def on_noop(self, channel: Channel, session: FBDPSession) -> None:
        """Called when NOOP message is received, and after ACK-REPLY (if requested) is send.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
        """
    @eventsocket
    def on_accept_data(self, channel: Channel, session: FBDPSession, data: bytes) -> None:
        """Event executed for CONSUMER to process data received in DATA message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
            data: Data received from client.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.

        Note:
            The ACK-REQUEST in received DATA message is handled automatically by protocol.
        """
    @eventsocket
    def on_produce_data(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Event executed for PRODUCER to store data into outgoing DATA message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
            msg: DATA message that will be sent to client.

        The event handler must store the data in `msg.data_frame` attribute. It may also
        set ACK-REQUEST flag and `type_data` attribute.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.

        Note:
            To indicate end of data, raise StopError with ErrorCode.OK code.
        """
    @eventsocket
    def on_data_confirmed(self, channel: Channel, session: FBDPSession, type_data: int) -> None:
        """Event executed for PRODUCER when ACK_REPLY on sent DATA is received.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            type_data: Content of `type_data` field from received DATA message confirmation.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.
        """
    @eventsocket
    def on_get_data(self, channel: Channel, session: FBDPSession) -> bool:
        """Event executed for PRODUCER to query the data source for data availability,
        and for CONSUMER to query whether data could be accepted.

        Important:
            If this event does not have handler assigned, the data source is considered as
            "stable" source that can always produce/consume data (for example data files
            are stable sources).

            For PRODUCERS, handler MUST return True if there are data available for sending.
            If handler returns False, the transmission will be suspended until its resumed
            via `Channel.set_wait_out(True)`.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.
        """
    @property
    def logging_id(self) -> str:
        "Returns _logging_id_ or <class_name>"
        return getattr(self, '_logging_id_', self.__class__.__name__)

class FBDPServer(_FBDP):
    """9/FBDP - Firebird Butler Data Pipe Protocol - Server side.
    """
    def __init__(self, *, session_type: Type[FBDPSession] = FBDPSession):
        """
        Arguments:
            session_type: Class for session objects.
        """
        super().__init__(session_type=session_type)
        # Session socket that means that messages flow to us (client connected to our INPUT)
        self._flow_in_socket: PipeSocket = PipeSocket.INPUT
        #
        self.on_accept_client = self.handle_accept_client
        self.on_get_ready = self.handle_get_ready
        self.on_schedule_ready = self.handle_schedule_ready
        #
        self.handlers.update({MsgType.OPEN: self.handle_open_msg,
                              MsgType.READY: self.handle_ready_msg,
                              })
    def _init_new_batch(self, channel: Channel, session: FBDPSession) -> None:
        """Initializes the transmission of a new batch of DATA messages.

        As we're server, we also have to send READY to the client.
        """
        session.transmit = None
        if (batch_size := self.on_get_ready(channel, session)) == 0:
            self.on_schedule_ready(channel, session)
        if batch_size is not None:
            ready = max(0, self.batch_size if batch_size == -1 else batch_size)
            self.send_ready(channel, session, ready)
            session.await_ready = True
    def handle_accept_client(self, channel: Channel, session: FBDPSession) -> None:
        """Default event handler that raises `StopError` exception with ErrorCode.INTERNAL_ERROR.
        """
        raise StopError("Accept handler not defined", code=ErrorCode.INTERNAL_ERROR)
    def handle_get_ready(self, channel: Channel, session: FBDPSession) -> int:
        """Default event handler that returns -1, unless `on_get_data` event handler is
        assigned and it returns False - then it returns 0.
        """
        if self.on_get_data.is_set() and not self.on_get_data(channel, session):
            return 0
        return -1
    def handle_schedule_ready(self, channel: Channel, session: FBDPSession) -> None:
        """Default event handler that raises `StopError` exception with ErrorCode.INTERNAL_ERROR.

        Note:
            This handler must be reasigned or overriden only when `on_get_ready` event
            handler may return zero.
        """
        raise StopError("READY scheduler not defined", code=ErrorCode.INTERNAL_ERROR)
    def resend_ready(self, channel: Channel, session: FBDPSession) -> None:
        """Send another ready to the client.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
        """
        # It's possible that session could be canceled before resend is called,
        # or transmission was already started, or READY was already sent and awaits
        # response from client. In such case we'll ignore this resend request.
        if (session.routing_id in channel.sessions
            and session.transmit is None
            and not session.await_ready):
            # This is called directly and not via `handle_msg()` and message handler, so
            # it's necessary to handle exceptions like `handle_msg()` does.
            try:
                self._init_new_batch(channel, session)
            except Exception as exc:
                try:
                    self.handle_exception(channel, session, FBDPMessage(), exc)
                except:
                    warnings.warn('Exception raised in exception handler', RuntimeWarning)
        else:
            if session.routing_id not in channel.sessions:
                warnings.warn('resend_ready: senssion cancelled', RuntimeWarning)
            elif session.transmit is not None:
                warnings.warn('resend_ready: transmission already started', RuntimeWarning)
            elif session.await_ready:
                warnings.warn('resend_ready: READY was already sent', RuntimeWarning)
            else:
                warnings.warn('resend_ready: programming error', RuntimeWarning)
    def handle_open_msg(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Process OPEN message received from client.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `handle_exception`.
        """
        if session.pipe is not None:
            # Client already attached to data pipe, OPEN out of band
            raise StopError("Out of band OPEN message", code=ErrorCode.PROTOCOL_VIOLATION)
        socket = PipeSocket(msg.data_frame.pipe_socket)
        session.pipe = msg.data_frame.data_pipe
        session.socket = socket
        session.data_format = msg.data_frame.data_format
        session.params.update(struct2dict(msg.data_frame.parameters))
        self.on_accept_client(channel, session)
        self._init_new_batch(channel, session)
        channel.on_output_ready = self._on_output_ready
    def handle_ready_msg(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Process READY message received from client.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `handle_exception`.
        """
        if not session.await_ready:
            # Transmission in progress, READY is out of band
            raise StopError("Out of band READY message",
                            code=ErrorCode.PROTOCOL_VIOLATION)
        session.await_ready = False
        if msg.type_data == 0:
            # Client either confirmed our zero, or is not ready yet.
            self.on_schedule_ready(channel, session)
        else:
            # All green to transmit DATA
            session.transmit = msg.type_data
            if session.socket is PipeSocket.OUTPUT:
                # Initiate transfer to output (via I/O loop)
                channel.set_wait_out(True, session)
    @eventsocket
    def on_accept_client(self, channel: Channel, session: FBDPSession) -> None:
        """Event executed when client connects to the data pipe via OPEN message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The session attributes `data_pipe`, `pipe_socket`, `data_format` and `params`
        contain information sent by client, and the event handler must validate the request.

        If request should be rejected, it must raise the `StopError` exception with `code`
        attribute containing the `ErrorCode` to be returned in CLOSE message.
        """
    @eventsocket
    def on_get_ready(self, channel: Channel, session: FBDPSession) -> int:
        """Event executed to obtain the transmission batch size for the client.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        Returns:
           Number of messages that could be transmitted (batch size):
           * 0 = Not ready to transmit yet
           * n = Ready to transmit 1..<n> messages.
           * -1 = Ready to transmit 1..<protocol batch size> messages.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.
        """
    @eventsocket
    def on_schedule_ready(self, channel: Channel, session: FBDPSession) -> None:
        """The event is executed in order to send the READY message to the client later.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.
        """

class FBDPClient(_FBDP):
    """9/FBDP - Firebird Butler Data Pipe Protocol - Client side.
    """
    def __init__(self, *, session_type: Type[FBDPSession] = FBDPSession):
        """
        Arguments:
            session_type: Class for session objects.
            batch_size: Default batch size.
        """
        super().__init__(session_type=session_type)
        # Session socket that means that messages flow to us (we are connected to server OUTPUT)
        self._flow_in_socket: PipeSocket = PipeSocket.OUTPUT
        self.on_server_ready = self.handle_server_ready
        #
        self.handlers.update({MsgType.OPEN: self.handle_open_msg,
                              MsgType.READY: self.handle_ready_msg,
                              })
    def handle_server_ready(self, channel: Channel, session: FBDPSession, batch_size: int) -> int:
        """Default event handler that returns -1, unless `on_get_data` event handler is
        assigned and it returns False - then it returns 0.
        """
        if self.on_get_data.is_set() and not self.on_get_data(channel, session):
            return 0
        return -1
    def _init_new_batch(self, channel: Channel, session: FBDPSession) -> None:
        """Initializes the transmission of a new batch of DATA messages.
        """
        session.transmit = None
    def accept_new_session(self, channel: Channel, routing_id: RoutingID,
                           msg: FBDPMessage) -> bool:
        """Validates incoming message that initiated new session/transmission.

        Arguments:
            channel:    Channel that received the message.
            routing_id: Routing ID of the sender.
            msg:        Received message.

        Returns:
            Always False (transmission must be initiated by Client).
        """
        return False
    def connect_with_session(self, channel: Channel) -> bool:
        """Called by :meth:`Channel.connect` to determine whether new session should be
        associated with connected peer.

        As FBDP require that connecting peers must send OPEN message to initiate
        transmission, it always returns True.
        """
        return True
    def handle_open_msg(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """OPEN message received from server is violation of the protocol.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `handle_exception`.
        """
        raise StopError("OPEN message received from server", ErrorCode.PROTOCOL_VIOLATION)
    def handle_ready_msg(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Process READY message received from server.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Note:
            All exceptions are handled by `handle_exception`.
        """
        if session.transmit is not None:
            # Transmission in progress, READY is out of band
            raise StopError("Out of band READY message",
                            code=ErrorCode.PROTOCOL_VIOLATION)
        if msg.type_data > 0:
            # Server is ready
            batch_size = self.on_server_ready(channel, session, msg.type_data)
            result = max(0, min(msg.type_data, self.batch_size if batch_size == -1 else batch_size))
            self.send_ready(channel, session, result)
            if result > 0:
                # We are ready to transmit as well
                session.transmit = result
                if session.socket is PipeSocket.INPUT:
                    # Initiate transfer to server (via I/O loop)
                    channel.set_wait_out(True, session)
        else:
            # Server is not ready, but we must send READY(0) back to confirm we've got it!
            self.send_ready(channel, session, 0)
    def send_open(self, channel: Channel, session: FBDPSession, data_pipe: str,
                  pipe_socket: PipeSocket, data_format: str, parameters: Dict=None) -> None:
        """Sends `OPEN` message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with transmission.
            data_pipe: Data pipe identification.
            pipe_socket: Connected pipe socket.
            data_format: Required data format.
            parameters: Data pipe parameters.

        Raises:
            StopError: When sending message fails.
        """
        msg = self.create_message_for(MsgType.OPEN)
        msg.data_frame.data_pipe = data_pipe
        msg.data_frame.pipe_socket = pipe_socket.value
        msg.data_frame.data_format = data_format
        if parameters:
            msg.data_frame.parameters.CopyFrom(dict2struct(parameters))
        if channel.send(msg, session) != 0:
            raise StopError("Broken pipe, can't send OPEN message", code=ErrorCode.ERROR)
        channel.on_output_ready = self._on_output_ready
        session.pipe = data_pipe
        session.socket = pipe_socket
        session.data_format = data_format
        if parameters:
            session.params.update(parameters)
        self.on_init_session(channel, session)
    @eventsocket
    def on_server_ready(self, channel: Channel, session: FBDPSession, batch_size: int) -> int:
        """Event executed to negotiate the transmission batch size with server.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with server.
            batch_size: Max. batch size accepted by server.

        Returns:
           Number of messages that could be transmitted (batch size):
           * 0 = Not ready to transmit yet
           * n = Ready to transmit 1..<n> messages.
           * -1 = Ready to transmit 1..<protocol batch size> messages.

        Important:
            The returned value will be used ONLY when it's smaller than `batch_size`.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.
        """
    @eventsocket
    def on_init_session(self, channel: Channel, session: FBDPSession) -> None:
        """Event executed from `send_open()` to set additional information to newly
        created session instance.
        """
