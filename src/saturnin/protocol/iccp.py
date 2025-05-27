# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/protocol/iccp.py
# DESCRIPTION:    Internal Component Control Protocol
# CREATED:        16.11.2020
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

"""Saturnin Internal Component Control Protocol (ICCP).

This protocol defines the messages and rules for communication between Saturnin
components (like services or microservices) and their controllers. It handles
lifecycle events (ready, stop, finished), configuration requests, and error reporting.
"""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Iterable
from enum import Enum, IntEnum
from struct import pack, unpack
from typing import Final

from saturnin.base import (
    PROTO_PEER,
    Channel,
    InvalidMessageError,
    Message,
    Outcome,
    PeerDescriptor,
    Protocol,
    RoutingID,
    Session,
    StopError,
    TZMQMessage,
)

from firebird.base import protobuf
from firebird.base.config import PROTO_CONFIG, Config, ConfigProto, ZMQAddress
from firebird.base.signal import eventsocket
from firebird.base.types import ANY


class MsgType(IntEnum):
    """Control message type.
    """
    READY = 1
    REQUEST = 2
    OK = 3
    ERROR = 4
    STOP = 5
    FINISHED = 6

class Request(Enum):
    """Controller Request Codes for ICCP.
    """
    CONFIGURE = b'CONF'

class ICCPMessage(Message):
    """Service Control Message.
    """
    def __init__(self):
        #: Type of message
        self.msg_type: MsgType = None
    def __str__(self):
        return f"{self.__class__.__qualname__}[{'NONE' if self.msg_type is None else self.msg_type.name}]"
    __repr__ = __str__
    def from_zmsg(self, zmsg: TZMQMessage) -> None:
        """Populate message data from sequence of ZMQ data frames.

        Arguments:
            zmsg: Sequence of ZMQ frames to be deserialized. The first frame is
            always the packed `MsgType`. Subsequent frames depend on the
            message type (e.g., peer info for `READY`, error string for `ERROR`).

        Raises:
            InvalidMessageError: If message is not a valid protocol message.
        """
        try:
            self.msg_type = MsgType(unpack('!H', zmsg[0])[0])
            if self.msg_type is MsgType.READY:
                proto = protobuf.create_message(PROTO_PEER, zmsg[1])
                self.peer = PeerDescriptor.from_proto(proto)
                proto = protobuf.create_message(protobuf.PROTO_STRUCT, zmsg[2])
                self.endpoints = {}
                for k, v in protobuf.struct2dict(proto).items():
                    for i in range(len(v)):
                        v[i] = ZMQAddress(v[i])
                    self.endpoints[k] = v
            elif self.msg_type is MsgType.ERROR:
                self.error = zmsg[1].decode('utf8')
            elif self.msg_type is MsgType.FINISHED:
                self.outcome = Outcome(zmsg[1].decode())
                self.details = [v.decode('utf8', errors='replace') for v in zmsg[2:]]
            elif self.msg_type is MsgType.REQUEST:
                self.request = Request(zmsg[1])
                if self.request is Request.CONFIGURE:
                    self.config = protobuf.create_message(PROTO_CONFIG, zmsg[2])
        except Exception as exc:
            raise InvalidMessageError("Invalid message") from exc
    def as_zmsg(self) -> TZMQMessage:
        """Returns message as sequence of ZMQ data frames.

        Returns:
            A list of ZMQ frames representing the message. The first frame is
            the packed `MsgType`. Subsequent frames are added based on the
            message type and its attributes.
        """
        try:
            zmsg = [pack('!H', self.msg_type)]
            if self.msg_type is MsgType.READY:
                zmsg.append(self.peer.as_proto().SerializeToString())
                zmsg.append(protobuf.dict2struct(self.endpoints).SerializeToString())
            elif self.msg_type is MsgType.ERROR:
                zmsg.append(self.error.encode('utf8', errors='replace'))
            elif self.msg_type is MsgType.FINISHED:
                zmsg.append(self.outcome.value.encode('utf-8', errors='replace'))
                zmsg.extend(v.encode('utf-8', errors='replace') for v in self.details)
            elif self.msg_type is MsgType.REQUEST:
                if self.request is Request.CONFIGURE:
                    zmsg.append(self.config.SerializeToString())
        except Exception:
            traceback.print_exc()
        return zmsg
    def clear(self) -> None:
        """Clears message data.
        """
        self.msg_type = None
        for attr in ('peer', 'endpoints', 'error', 'request', 'config'):
            if hasattr(self, attr):
                delattr(self, attr)
    def copy(self) -> Message:
        """Returns copy of the message.

        Returns:
            A new `ICCPMessage` instance with a deep copy of relevant
            attributes (like `peer`, `endpoints`, `config`) based on the
            original message's `msg_type`.
        """
        msg = self.__class__()
        msg.msg_type = self.msg_type
        if self.msg_type is MsgType.READY:
            msg.peer = self.peer.copy()
            msg.endpoints = self.endpoints.copy()
        elif self.msg_type is MsgType.ERROR:
            msg.error = self.error
        elif self.msg_type is MsgType.REQUEST:
            msg.request = self.request
            if self.request is Request.CONFIGURE:
                msg.config = protobuf.create_message(PROTO_CONFIG)
                msg.config.CopyFrom(self.config)
        return msg
    def get_keys(self) -> Iterable:
        """Returns iterable of dictionary keys to be used with `.Protocol.handlers`.
        Keys must be provided in order of precedence (from more specific to general).
        """
        return [self.msg_type, ANY]

class _ICCP(Protocol):
    """Internal Component Control Protocol (ICCP).

    Used by Saturnin internally for component/controller transmissions.
    """
    #: string with protocol OID (dot notation).
    OID: Final[str] = '1.3.6.1.4.1.53446.1.1.0.1.1'
    # iso.org.dod.internet.private.enterprise.firebird.butler.platform.saturnin.protocol.iscp
    #: UUID instance that identifies the protocol.
    UID: Final[uuid.UUID] = uuid.uuid5(uuid.NAMESPACE_OID, OID)
    def __init__(self, *, session_type: type[Session] = Session):
        """
        Arguments:
            session_type: Class for session objects.
        """
        super().__init__(session_type=session_type)
        self._msg: ICCPMessage = ICCPMessage()
        self.message_factory = self.__message_factory
    def __message_factory(self, zmsg: TZMQMessage | None=None) -> Message:
        "Internal message factory"
        self._msg.clear()
        return self._msg
    def validate(self, zmsg: TZMQMessage) -> None:
        """Verifies that sequence of ZMQ data frames is a valid protocol message.

        If this validation passes without exception, then `.parse()` of the same message
        must be successful as well.

        Arguments:
            zmsg:   ZeroMQ multipart message. Expects the first frame to be the
                    packed `MsgType`, followed by type-specific frames.

        Raises:
            InvalidMessageError: If ZMQ message is not a valid protocol message.
        """
        if not zmsg:
            raise InvalidMessageError("Empty message")
        try:
            msg_type = MsgType(unpack('!H', zmsg[0]))
        except Exception as exc:
            raise InvalidMessageError("Invalid message type") from exc
        if msg_type is MsgType.READY:
            try:
                PeerDescriptor.from_proto(protobuf.create_message(PROTO_PEER, zmsg[1]))
            except Exception as exc:
                raise InvalidMessageError("Invalid data: peer descriptor") from exc
            try:
                protobuf.create_message(protobuf.PROTO_STRUCT, zmsg[2])
            except Exception as exc:
                raise InvalidMessageError("Invalid data: endpoints") from exc
        elif msg_type is MsgType.ERROR:
            try:
                zmsg[1].decode('utf8')
            except Exception as exc:
                raise InvalidMessageError("Invalid data: error message") from exc
        elif msg_type is MsgType.REQUEST:
            try:
                req = Request(zmsg[1])
            except Exception as exc:
                raise InvalidMessageError("Invalid request code") from exc
            if req is Request.CONFIGURE:
                try:
                    protobuf.create_message(PROTO_CONFIG, zmsg[2])
                except Exception as exc:
                    raise InvalidMessageError("Invalid data: config") from exc

class ICCPComponent(_ICCP):
    """Internal Component Control Protocol (ICCP) - Component (client) side.

    Used by Saturnin internally for component/controller transmissions.
    """
    def __init__(self, *, session_type: type[Session] = Session, with_traceback: bool=False):
        """
        Arguments:
            session_type: Class for session objects.
            with_traceback: When True, stores traceback along with exception in ERROR/FINISHED.
        """
        super().__init__(session_type=session_type)
        self.with_traceback: bool = with_traceback
        self.handlers.update({MsgType.READY: self.wrong_message,
                              MsgType.REQUEST: self.handle_request,
                              MsgType.OK: self.wrong_message,
                              MsgType.ERROR: self.wrong_message,
                              MsgType.STOP: self.handle_stop,
                              MsgType.FINISHED: self.wrong_message,
                              })
    def accept_new_session(self, channel: Channel, routing_id: RoutingID,
                           msg: ICCPMessage) -> bool:
        """Validates incoming message that initiated new session/transmission.

        Arguments:
            channel:    Channel that received the message.
            routing_id: Routing ID of the sender.
            msg:        Received message.

        Returns:
            Always False (transmission must be initiated by Component).
        """
        return False
    def connect_with_session(self, channel: Channel) -> bool:
        """Called by :meth:`Channel.connect` to determine whether new session should be
        associated with connected peer.

        As ICCP require that connecting peers must send a message to initiate transmission,
        it always returns True.

        Arguments:
          channel: Channel associated with controller.
        """
        return True
    def wrong_message(self, channel: Channel, session: Session, msg: ICCPMessage) -> None:
        """Handle wrong message received from controller.

        Arguments:
          channel: Channel associated with controller.
          session: Session associated with controller.
          msg:     Message sent by controller.

        Raises `.StopError`, which in turn calls `.on_exception` from `.handle_msg`.
        """
        raise StopError("Wrong message received from controller")
    def handle_invalid_msg(self, channel: Channel, session: Session,
                           exc: InvalidMessageError) -> None:
        """Event handler for `.on_invalid_msg`. Calls `on_stop_component` with exception.

        Arguments:
          channel: Channel associated with controller.
          session: Session associated with controller.
          exc:     Exception raised.
        """
        self.on_stop_component(exc)
        super().handle_invalid_msg(channel, session, exc)
    def handle_exception(self, channel: Channel, session: Session, msg: ICCPMessage,
                         exc: Exception) -> None:
        """Event handler for `.on_exception`. Calls `on_stop_component` with exception.

        Arguments:
          channel: Channel associated with controller.
          session: Session associated with controller.
          msg:     Message sent by controller.
          exc:     Exception to handle.
        """
        self.on_stop_component(exc)
        super().handle_exception(channel, session, msg, exc)
    def handle_stop(self, channel: Channel, session: Session, msg: ICCPMessage) -> None:
        """Process `STOP` message received from controller. Calls `on_stop_component`.

        Arguments:
          channel: Channel associated with controller.
          session: Session associated with controller.
          msg:     Received message.
        """
        self.on_stop_component()
    def handle_request(self, channel: Channel, session: Session, msg: ICCPMessage) -> None:
        """Process `REQUEST` message received from controller.

        Currently handles `Request.CONFIGURE` by invoking the `on_config_request`
        event with the provided configuration. Sends an `OK` message back to the
        controller upon successful processing, or an `ERROR` message if an
        exception occurs during the `on_config_request` handling.

        Arguments:
            channel: The channel connected to the controller.
            session: The session instance for this communication.
            msg: The received `ICCPMessage` containing the request.

        Raises:
            StopError: If sending the response (OK/ERROR) to the controller fails.
        """
        result = self.ok_msg()
        try:
            # Right now we have only one type of Request - CONFIGURE
            self.on_config_request(msg.config)
        except Exception as exc:
            result = self.error_msg(exc)
        if not (err_code := channel.send(result, session)):
            raise StopError("Send to controller failed", err_code=err_code)
    def ready_msg(self, peer: PeerDescriptor,
                  endpoints: dict[str, list[ZMQAddress]]) -> ICCPMessage:
        """Returns `READY` control message.

        Arguments:
          peer:      Component descriptor.
          endpoints: Component endpoints.
        """
        msg: ICCPMessage = self.message_factory()
        msg.msg_type = MsgType.READY
        msg.peer = peer.copy()
        msg.endpoints = endpoints.copy()
        return msg
    def ok_msg(self) -> ICCPMessage:
        """Returns `OK` control message.
        """
        msg: ICCPMessage = self.message_factory()
        msg.msg_type = MsgType.OK
        return msg
    def error_msg(self, exc: Exception) -> ICCPMessage:
        """Returns `ERROR` control message.

        Arguments:
          exc: Exception to send.
        """
        msg: ICCPMessage = self.message_factory()
        msg.msg_type = MsgType.ERROR
        if self.with_traceback:
            msg.error = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        else:
            msg.error = str(exc)
        return msg
    def finished_msg(self, outcome: Outcome,
                     details: None | Exception | list[str]) -> ICCPMessage:
        """Returns `FINISHED` control message.

        Arguments:
          outcome: Outcome of componentn run.
          details: Additional information about the outcome.
                   If an `Exception`, its traceback (if `with_traceback` is True)
                   or string, string representation is used. If a `list[str]`, it's used
                   directly. If `None`, no details are included.
        """
        msg: ICCPMessage = self.message_factory()
        msg.msg_type = MsgType.FINISHED
        msg.outcome = outcome
        if isinstance(details, Exception):
            if self.with_traceback:
                msg.details = traceback.format_exception(type(details), details,
                                                         details.__traceback__)
            else:
                msg.details = repr(details)
        elif details is None:
            msg.details = []
        else:
            msg.details = details.copy()
        return msg
    @eventsocket
    def on_stop_component(self, exc: Exception | None=None) -> None:
        """`~firebird.base.signal.eventsocket` called when commponent should stop its operation.

        Arguments:
           exc: Exception that describes the reason why component should stop. If not
                provided, the component should stop on controller's request.
        """
    @eventsocket
    def on_config_request(self, config: ConfigProto) -> None:
        """`~firebird.base.signal.eventsocket` called when the controller requests reconfiguration.

        The handler should apply the new configuration. Any exception raised by
        this event handler will be caught and sent back to the controller as an
        `ERROR` message.

        Arguments:
           config: The new configuration (`~firebird.base.config.ConfigProto`)
                   provided by the controller.
        """

class ICCPController(_ICCP):
    """Internal Component Control Protocol (ICCP) - Controller (server) side.

    Used by Saturnin internally for component/controller transmissions.
    """
    def __init__(self, *, session_type: type[Session] = Session):
        """
        Arguments:
            session_type: Class for session objects.
        """
        super().__init__(session_type=session_type)
        self.handlers.update({MsgType.READY: self.handle_ready,
                              MsgType.REQUEST: self.wrong_message,
                              MsgType.OK: self.handle_oef,
                              MsgType.ERROR: self.handle_oef,
                              MsgType.STOP: self.wrong_message,
                              MsgType.FINISHED: self.handle_oef,
                              })
    def wrong_message(self, channel: Channel, session: Session, msg: ICCPMessage) -> None:
        """Handle wrong message received from component.

        Arguments:
          channel: Channel associated with component.
          session: Session associated with component.
          msg:     Message sent by component.

        Raises `.StopError`, which in turn calls `.on_exception` from `.handle_msg`.
        """
        raise StopError("Wrong message received from component")
    def handle_invalid_msg(self, channel: Channel, session: Session,
                           exc: InvalidMessageError) -> None:
        """Event handler for `.on_invalid_msg`. Calls `on_stop_controller` with exception.

        Arguments:
          channel: Channel associated with component.
          session: Session associated with component.
          exc:     Exception raised.
        """
        self.on_stop_controller(exc)
        super().handle_invalid_msg(channel, session, exc)
    def handle_exception(self, channel: Channel, session: Session, msg: ICCPMessage,
                         exc: Exception) -> None:
        """Event handler for `.on_exception`. Calls `on_stop_controller` with exception.

        Arguments:
          channel: Channel associated with component.
          session: Session associated with component.
          msg:     Message sent by component.
          exc:     Exception to handle.
        """
        self.on_stop_controller(exc)
        super().handle_exception(channel, session, msg, exc)
    def handle_ready(self, channel: Channel, session: Session, msg: ICCPMessage) -> ICCPMessage:
        """Processes a `READY` message received from a component.

        If this is the first `READY` message for the session (indicated by
        `session.ready` not being set), it marks the session as ready and
        returns the received message. This typically signals that the component
        is initialized and has provided its peer information and endpoints.

        Arguments:
            channel: Channel associated with the component.
            session: Session associated with the component.
            msg: The `READY` message sent by the component.

        Returns:
            The received `ICCPMessage` if it's the first `READY` for this session.

        Raises:
            StopError: If a `READY` message is received for a session already marked as ready,
                       as this indicates an unexpected state.
        """
        if hasattr(session, 'ready'):
            raise StopError("Unexpected READY message from component")
        session.ready = True
        return msg
    def handle_oef(self, channel: Channel, session: Session, msg: ICCPMessage) -> ICCPMessage:
        """Process `OK/ERROR/FINISHED` messages received from component. It simply returns
        the message.

        Arguments:
          channel: Channel associated with component.
          session: Session associated with component.
          msg:     Message sent by component.
        """
        if msg.msg_type in (MsgType.OK, MsgType.FINISHED) and not hasattr(session, 'ready'):
            raise StopError(f"Unexpected {msg.msg_type.name} message from component")
        return msg
    def stop_msg(self) -> ICCPMessage:
        """Returns `STOP` control message.
        """
        msg: ICCPMessage = self.message_factory()
        msg.msg_type = MsgType.STOP
        return msg
    def request_config_msg(self, config: Config | None=None) -> ICCPMessage:
        """Returns `REQUEST.CONFIG` control message.

        Arguments:
          config: Optional `firebird.base.config.Config` instance containing the
                  configuration for the component. If `None`, an empty configuration
                  request is created.
        """
        msg: ICCPMessage = self.message_factory()
        msg.msg_type = MsgType.REQUEST
        msg.request = Request.CONFIGURE
        msg.config = protobuf.create_message(PROTO_CONFIG)
        if config:
            config.save_proto(msg.config)
        return msg
    @eventsocket
    def on_stop_controller(self, exc: Exception) -> None:
        """`~firebird.base.signal.eventsocket` called when controller should stop its
        operation due to error condition.

        Arguments:
           exc: Exception that describes the reason why component should stop.
        """
