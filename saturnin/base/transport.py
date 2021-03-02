#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/transport.py
# DESCRIPTION:    ZeroMQ messaging - base classes and other definitions
# CREATED:        28.2.2019
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

"Saturnin ZeroMQ messaging - base classes and other definitions"

from __future__ import annotations
from typing import  Union, Dict, List, Iterable, Callable, Optional, Type, Any
from abc import ABC, abstractmethod
from weakref import proxy
import uuid
import warnings
import zmq
from zmq import Frame, ZMQError, Again, POLLIN, POLLOUT
from firebird.base.types import ZMQAddress, DEFAULT, UNDEFINED, ANY
from firebird.base.signal import eventsocket
from firebird.base.logging import LoggingIdMixin
from firebird.base.trace import TracedMixin
from .types import RoutingID, SocketMode, SocketType, Direction, \
     InvalidMessageError, ChannelError, INVALID, TIMEOUT

#: Internal routing ID
INTERNAL_ROUTE: RoutingID = b'INTERNAL'

class ChannelManager(LoggingIdMixin, TracedMixin):
    """Manager of ZeroMQ communication channels.
    """
    def __init__(self, context: zmq.Context):
        """
        Arguments:
            context: ZMQ Context instance.
        """
        #: ZMQ Context instance.
        self.ctx: zmq.Context = context
        #: Dictionary with managed channels. Key is `Channel.name`, value is the `Channel`.
        self.channels: Dict[str, Channel] = {}
        #: Logging context
        self.log_context: Any = UNDEFINED
        self._poller: zmq.Poller = None
        self._chmap: Dict[zmq.Socket, Channel] = {}
        self._pollout: bool = False
    def create_channel(self, cls: Type[Channel], name: str, protocol: Protocol, *,
                       routing_id: RoutingID=DEFAULT, session_type: Type[Session]=DEFAULT,
                       wait_for: Direction=Direction.NONE,
                       snd_timeout: int=100, rcv_timeout: int=100,
                       linger: int=5000, sock_opts: TSocketOptions=None) -> Channel:
        """Creates new channel.

        Arguments:
            cls: Channel class.
            name: Channel name.
            routing_id: Channel socket identity (routing ID for peers).
            protocol: Protocol for serializing/deserializing messages.
            session_type: Session type. DEFAULT session type is obtained from MessageHandler.
            wait_for: Direction(s) of transmission events for this channel processed by `.wait()`.
            snd_timeout: Timeout for send operation in milliseconds, None means infinite.
            rcv_timeout: Timeout for receive operation in milliseconds, None means infinite.
            linger: ZMQ socket linger period.
            sock_opts: Dictionary with socket additional options.
        """
        assert name not in self.channels, "Duplicate channel name"
        chn: Channel = cls(self, name, protocol, routing_id, session_type, wait_for,
                           snd_timeout, rcv_timeout, linger, sock_opts)
        self.channels[chn.name] = chn
        return chn
    def update_poller(self, channel: Channel, value: Direction) -> None:
        """Update poller registration for channel.
        """
        self._pollout = False
        for chn in self.channels.values():
            self._pollout = self._pollout or Direction.OUT in chn.wait_for
        if self._poller is not None:
            self._poller.modify(channel.socket, value.value)
    def has_pollout(self) -> bool:
        """Returns True if :meth:`wait` will check for POLLOUT event on any channel.
        """
        return self._pollout
    def wait(self, timeout: int=None) -> Dict[Channel, Direction]:
        """Wait for I/O events on channnels.

        Arguments:
            timeout: The timeout in milliseconds. `None` value means `infinite`.

        Returns:
            Dictionary with channel keys and event values.
        """
        if self._poller is None:
            self._poller = zmq.Poller()
            self._pollout = False
            for chn in self.channels.values():
                self._pollout = self._pollout or Direction.OUT in chn.wait_for
                self._poller.modify(chn.socket, chn.wait_for.value)
        return {self._chmap[socket]: Direction(e) for socket, e in self._poller.poll(timeout)}
    def warm_up(self) -> None:
        """Create and set up ZMQ sockets for all registered channels that does not have socket.
        """
        for chn in self.channels.values():
            if chn.socket is None:
                chn.set_socket(self.ctx.socket(chn.socket_type.value))
                self._chmap[chn.socket] = chn
    def shutdown(self, *, forced: bool=False) -> None:
        """Close all managed channels.

        Calls unbind/disconnect on active channels, and clears all sessions.

        Arguments:
            forced: When True, channels are closed with zero LINGER and all ZMQ errors are
                    ignored.
        """
        self._chmap = {}
        for chn in self.channels.values():
            if (self._poller is not None) and (chn.wait_for != Direction.NONE):
                self._poller.unregister(chn.socket)
            try:
                chn.on_shutdown(chn, forced)
            except:
                pass
            try:
                if chn.mode is SocketMode.BIND:
                    chn.unbind()
                elif chn.mode is SocketMode.CONNECT:
                    chn.disconnect()
            except:
                pass
            chn.sessions.clear()
            if forced:
                chn.drop_socket()
            else:
                chn.close_socket()


class Message(ABC):
    """Abstract base class for protocol message.
    """
    def __str__(self):
        return self.__class__.__qualname__
    __repr__ = __str__
    @abstractmethod
    def from_zmsg(self, zmsg: TZMQMessage) -> None:
        """Populate message data from sequence of ZMQ data frames.

        Arguments:
            zmsg: Sequence of frames that should be deserialized.

        Raises:
            InvalidMessageError: If message is not a valid protocol message.
        """
    @abstractmethod
    def as_zmsg(self) -> TZMQMessage:
        """Returns message as sequence of ZMQ data frames.
        """
    @abstractmethod
    def clear(self) -> None:
        """Clears message data.
        """
    @abstractmethod
    def copy(self) -> Message:
        """Returns copy of the message.
        """
    @abstractmethod
    def get_keys(self) -> Iterable:
        """Returns iterable of dictionary keys to be used with `Protocol.handlers`.
        Keys must be provided in order of precedence (from more specific to general).
        """

class SimpleMessage(Message):
    """Simple protocol message that holds items from ZMQ multipart message in its
    :attr:`.data` attribute.
    """
    def __init__(self):
        #: Sequence of data frames
        self.data: List[bytes] = []
    def from_zmsg(self, zmsg: TZMQMessage) -> None:
        """Populate message data from sequence of ZMQ data frames.

        Arguments:
            zmsg: Sequence of frames that should be deserialized.

        Raises:
            InvalidMessageError: If message is not a valid protocol message.

        Important:
            This class just makes a copy of items from ZMQ message list into :attr:`data`.
            All `~zmq.Frame` items are 'unpacked' into bytes, other items are simply copied.
        """
        self.data = [i.bytes if isinstance(i, zmq.Frame) else i for i in zmsg]
    def as_zmsg(self) -> TZMQMessage:
        """Returns message as sequence of ZMQ data frames.

        Important:
            This class simply returns the list kept in :attr:`.data` attribute. This may
            cause problems if returned list is subsequently updated. In such a case, create
            a copy of returned list, or create a subclass that overrides this method.
        """
        return self.data
    def clear(self) -> None:
        """Clears message data.
        """
        self.data.clear()
    def copy(self) -> Message:
        """Returns copy of the message.
        """
        msg = Message()
        msg.data = self.data.copy()
        return msg
    def get_keys(self) -> Iterable:
        """Returns iterable of dictionary keys to be used with `Protocol.handlers`.

        The default implementation returns list with first data frame or None, ANY sentinel.
        """
        return [self.data[0] if self.data else None, ANY]

class Session:
    """Base Peer Session class.
    """
    def __init__(self):
        #: Channel routing ID for connected peer
        self.routing_id: RoutingID = None
        #: Connected endpoint address, if any
        self.endpoint: Optional[ZMQAddress] = None
        #: Flag indicating that session is waiting for send
        self.send_pending: bool = False
    def __str__(self):
        return self.logging_id
    __repr__ = __str__
    @property
    def logging_id(self) -> str:
        "Returns _logging_id_ or <class_name>[<routing_id>:<endpoint>]"
        return getattr(self, '_logging_id_',
                       f'{self.__class__.__name__}[{self.routing_id}:{self.endpoint}]')

class Protocol(TracedMixin):
    """Base class for protocol.

    The main purpose of protocol class is to validate ZMQ messages, create protocol
    messages and session objects used by `Channel` to manage transmissions, and to handle
    messages received from channel. This base class defines common interface for message
    convertsion and validation. Descendant classes typically add methods for creation
    of protocol messages and message handling.
    """
    #: string with protocol OID (dot notation). MUST be set in child class.
    OID: str = '1.3.6.1.4.1.53446.1.5' # iso.org.dod.internet.private.enterprise.firebird.butler.protocol
    #: UUID instance that identifies the protocol. MUST be set in child class.
    UID: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_OID, OID)
    #: Protocol revision (default 1)
    REVISION: int = 1
    def __init__(self, *, session_type: Type[Session]=Session):
        """
        Arguments:
            session_type: Class for session objects.
        """
        self._session_type: Type[Session] = session_type
        #: Callable that returns `.Message` instance
        self.message_factory = self.__message_factory
        #: Message handlers
        self.handlers: Dict[Any, TMessageHandler] = {}
    def __message_factory(self, zmsg: TZMQMessage=None) -> Message:
        "Internal message factory"
        return SimpleMessage()
    def __str__(self):
        return self.logging_id
    __repr__ = __str__
    def is_valid(self, zmsg: TZMQMessage) -> bool:
        """Return True if ZMQ message is a valid protocol message, otherwise returns False.

        Exceptions other than `~saturnin.core.types.InvalidMessageError` are not caught.

        Arguments:
            zmsg: ZeroMQ multipart message.
        """
        try:
            self.validate(zmsg)
        except InvalidMessageError:
            return False
        else:
            return True
    def validate(self, zmsg: TZMQMessage) -> None:
        """Verifies that sequence of ZMQ data frames is a valid protocol message.

        If this validation passes without exception, then `.convert_msg()` of the same
        message must be successful as well.

        Important:
            Implementation in base Protocol performs no validation and always returns True.

        Arguments:
            zmsg:   ZeroMQ multipart message.

        Raises:
            InvalidMessageError: If ZMQ message is not a valid protocol message.
        """
    def convert_msg(self, zmsg: TZMQMessage) -> Message:
        """Converts ZMQ message into protocol message.

        Arguments:
            zmsg: ZeroMQ multipart message.

        Returns:
            New protocol message instance with parsed ZMQ message. The base Protocol
            implementation returns `.Message` instance created by message factory.

        Raises:
            InvalidMessageError: If message is not a valid protocol message.
        """
        msg = self.message_factory(zmsg)
        msg.from_zmsg(zmsg)
        return msg
    def accept_new_session(self, channel: Channel, routing_id: RoutingID, msg: Message) -> bool:
        """Validates incoming message that initiated new session/transmission.

        Important:
            Default implementation unconditionally accept new sessions (always returns True).

        Arguments:
            channel:    Channel that received the message.
            routing_id: Routing ID of the sender.
            msg:        Received message.
        """
        return True
    def connect_with_session(self, channel: Channel) -> bool:
        """Called by :meth:`Channel.connect` to determine whether new session should be
        associated with connected peer.

        Note:
            Because it's not possible to call `Channel.send` without session, all protocols
            that require connecting peers to send a message to initiate transmission must
            return True.

            The default implementation uses :attr:`Channel.direction` to determine the
            return value (True if it contains `Direction.OUT`, else False).
        """
        return Direction.OUT in channel.direction
    def initialize_session(self, session: Session) -> None:
        """Initialize new session instance. The default implementation does nothing.
        """
    def handle_msg(self, channel: Channel, session: Session, msg: Message) -> Any:
        """Process message received from peer.

        Arguments:
            channel: Channel that received the message.
            session: Session instance.
            msg:     Received message.

        Uses :attr:`handlers` dictionary and `.Message.get_keys()` to select and execute
        the message handler. Exceptions raised by message handler are processed by
        `on_exception` event handler (if assigned). Exceptions raised by event handler are
        ignored, only `RuntimeWarning` is emitted.

        Returns:
            Whatever handler returns, or None when handler raises an exception.
        """
        handler: TMessageHandler = None
        for key in msg.get_keys():
            if handler := self.handlers.get(key):
                break
        try:
            assert handler, "Message without handler"
            return handler(channel, session, msg)
        except Exception as exc:
            try:
                self.handle_exception(channel, session, msg, exc)
            except:
                warnings.warn('Exception raised in exception handler', RuntimeWarning)
        return INVALID
    def handle_invalid_msg(self, channel: Channel, session: Session, exc: InvalidMessageError) -> None:
        """Called by `.Channel.receive()` when message conversion raises `InvalidMessageError`.

        Important:
            Executes `.on_invalid_msg` event. Descendant classes that override this method
            must call super() or execute this event directly.

            If this method is not overriden by descendant, and handler for this event is
            not defined, all `InvalidMessageError` exceptions are silently ignored.
        """
        self.on_invalid_msg(channel, session, exc)
    def handle_exception(self, channel: Channel, session: Session, msg: Message, exc: Exception) -> None:
        """Called by `.handle_msg()` on exception in message handler.

        Important:
            Executes `.on_exception` event. Descendant classes that override this method
            must call super() or execute this event directly.

            If this method is not overriden by descendant, and handler for this event is
            not defined, all exceptions raised in message handlers are silently ignored.
        """
        self.on_exception(channel, session, msg, exc)
    @eventsocket
    def message_factory(self, zmsg: TZMQMessage=None) -> Message:
        """Message factory that must return protocol message instance.
        The default factory produces new `SimpleMessage` instance on each call.
        """
    @eventsocket
    def on_invalid_msg(self, channel: Channel, session: Session, exc: InvalidMessageError) -> None:
        """Event called by `.Channel.receive()` when message conversion raises `InvalidMessageError`.

        Important:
            If handler for this event is not defined, all `InvalidMessageError` exceptions
            are silently ignored.
        """
    @eventsocket
    def on_exception(self, channel: Channel, session: Session, msg: Message, exc: Exception) -> None:
        """Event called by `.handle_msg()` on exception in message handler.

        Important:
            If handler for this event is not defined, all exceptions raised in message
            handlers are silently ignored.

            The exception thrown in this event handler is also not handled, and propagates
            to the upper layers (usually an I/O loop).
        """
    @property
    def session_type(self) -> Type[Session]:
        "Class for session objects."
        return self._session_type
    @property
    def logging_id(self) -> str:
        "Returns _logging_id_ or <class_name>[<uid>/<revision>]"
        return getattr(self, '_logging_id_', f'{self.__class__.__name__}[{self.UID.hex}/{self.REVISION}]')

class Channel(TracedMixin):
    """Base Class for ZMQ communication channel (socket).
    """
    def __init__(self, mngr: ChannelManager, name: str, protocol: Protocol,
                 routing_id: RoutingID, session_type: Type[Session], wait_for: Direction,
                 snd_timeout: int, rcv_timeout: int, linger: int, sock_opts: TSocketOptions):
        """
        Arguments:
            mngr: Channel manager.
            name: Channel name.
            routing_id: Routing ID for ZMQ socket.
            protocol: Protocol for serializing/deserializing messages.
            session_type: Session type. `DEFAULT` session type is obtained from Protocol.
            wait_for: Direction(s) of transmission events for this channel processed by
                      `ChannelManager.wait()`.
            snd_timeout: Timeout for send operation on the socket in milliseconds.
            rcv_timeout: Timeout for receive operation on the socket in milliseconds.
            linger: ZMQ socket linger period.
            sock_opts: Dictionary with socket options that should be set after socket creation.
        """
        self._mngr: ChannelManager = proxy(mngr)
        self._name = name
        self._routing_id: RoutingID = \
            uuid.uuid1().hex.encode() if routing_id is DEFAULT else routing_id
        self._protocol: Protocol = protocol
        self._session_type: Type[Session] = \
            protocol.session_type if session_type is DEFAULT else session_type
        self._snd_timeout: int = snd_timeout
        self._rcv_timeout: int = rcv_timeout
        self._linger: int = linger
        self._wait_for: Direction = wait_for
        self._mode: SocketMode = SocketMode.UNKNOWN
        self._socket_type: SocketType = SocketType.UNKNOWN_TYPE
        self._direction: Direction = Direction.BOTH
        #: ZMQ socket for transmission of messages
        self.socket: zmq.Socket = None
        #: Dictionary with socket options that should be set after socket creation
        self.sock_opts: TSocketOptions = sock_opts if sock_opts else dict()
        #: True if channel uses internal routing
        self.routed: bool = False
        #: List of binded/connected endpoints
        self.endpoints: List[ZMQAddress] = []
        #: Dictionary of active sessions, key=routing_id
        self.sessions: Dict[RoutingID, Session] = {}
        self._adjust()
    def __str__(self):
        return self.logging_id
    __repr__ = __str__
    def _adjust(self):
        """Called by `__init__()` to configure the channel parameters.
        """
    def set_socket(self, socket: zmq.Socket) -> None:
        """Used by `ChannelManager` to set socket to be used by `Channel`.
        """
        assert self.socket is None, "Channel socket is already set"
        self.socket = socket
        if self._routing_id:
            self.socket.routing_id = self._routing_id
        self.socket.immediate = 1
        self.socket.sndtimeo = self._snd_timeout
        self.socket.rcvtimeo = self._rcv_timeout
        self.socket.linger = self._linger
        if self.sock_opts:
            for name, value in self.sock_opts.items():
                setattr(self.socket, name, value)
        self._configure()
    def _configure(self) -> None:
        """Called by `.set_socket()` to configure the 0MQ socket.
        """
    def close_socket(self) -> None:
        """Close the ZMQ socket.

        Note:
            This will not change the linger value for socket, so underlying socket may not
            close if there are undelivered messages. The socket is actually closed only
            after all messages are delivered or discarded by reaching the socket’s LINGER
            timeout.
        """
        if self.socket and not self.socket.closed:
            self.socket.close()
        self.socket = None
    def drop_socket(self) -> None:
        """Unconditionally drops the ZMQ socket and all pending messages (forces LINGER=0).

        Note:
            All ZMQ errors raised by this operation are silently ignored.
        """
        try:
            if self.socket and not self.socket.closed:
                self.socket.close(0)
        except ZMQError:
            pass
        self.socket = None
    def create_session(self, routing_id: RoutingID) -> Session:
        """Returns newly created session.

        Arguments:
            routing_id: Routing ID for new session.

        Raises:
            ChannelError: When session for specified `routing_id` already exists.
        """
        if routing_id in self.sessions:
            raise ChannelError(f"Session for route {routing_id} already exists")
        session = self._session_type()
        session.routing_id = routing_id
        self.sessions[routing_id] = session
        self.protocol.initialize_session(session)
        return session
    def discard_session(self, session: Session) -> None:
        """Discard session object.

        If `.Session.endpoint` value is set, it also disconnects channel from this endpoint.

        Arguments:
            session: The Session to be discarded.
        """
        assert session.routing_id in self.sessions
        if session.endpoint:
            self.disconnect(session.endpoint)
        del self.sessions[session.routing_id]
    def bind(self, endpoint: ZMQAddress) -> ZMQAddress:
        """Bind the 0MQ socket to an address.

        Returns:
            The endpoint address. The returned address MAY differ from original address
            when wildcard specification is used.

        Raises:
            ChannelError: On attempt to a) bind another endpoint for PAIR socket, or
                b) bind to already binded endpoint.
        """
        assert self.socket is not None
        assert self.mode != SocketMode.CONNECT
        if (self.socket.socket_type == SocketType.PAIR) and self.endpoints:
            raise ChannelError("Cannot open multiple endpoints for PAIR socket")
        if endpoint in self.endpoints:
            raise ChannelError(f"Endpoint '{endpoint}' already openned")
        self.socket.bind(endpoint)
        endpoint = ZMQAddress(str(self.socket.last_endpoint, 'utf8'))
        self._mode = SocketMode.BIND
        self.endpoints.append(endpoint)
        return endpoint
    def unbind(self, endpoint: ZMQAddress=None) -> None:
        """Unbind from an address (undoes a call to `bind()`).

        Arguments:
            endpoint: Endpoint address, or None to unbind from all binded endpoints.
                      Note: The address must be the same as the addresss returned by `.bind()`.

        Raises:
            ChannelError: If channel is not binded to specified `endpoint`.
        """
        assert self.socket is not None
        assert self.mode == SocketMode.BIND
        if endpoint and endpoint not in self.endpoints:
            raise ChannelError(f"Endpoint '{endpoint}' not binded")
        addrs = [endpoint] if endpoint else list(self.endpoints)
        for addr in addrs:
            self.socket.unbind(addr)
            self.endpoints.remove(addr)
        if not self.endpoints:
            self._mode = SocketMode.UNKNOWN
    def connect(self, endpoint: ZMQAddress, *, routing_id: RoutingID=None) -> Optional[Session]:
        """Connect to a remote channel.

        Arguments:
            endpoint:   Endpoint address for connected peer.
            routing_id: Channel routing ID (required for routed channels).

        Returns:
            Session associated with connected peer, or None if no session was created.

        Raises:
            ChannelError: On attempt to a) connect another endpoint for PAIR socket, or
                b) connect to already connected endpoint.
        """
        assert self.socket is not None
        assert self.mode != SocketMode.BIND
        if (self.socket.socket_type == SocketType.PAIR) and self.endpoints:
            raise ChannelError("Cannot connect multiple endpoints for PAIR socket")
        if endpoint in self.endpoints:
            raise ChannelError(f"Endpoint '{endpoint}' already connected")
        if self.routed:
            assert routing_id
        else:
            routing_id = INTERNAL_ROUTE
        session = None
        if self.protocol.connect_with_session(self):
            session = self.create_session(routing_id)
            session.endpoint = endpoint
        if self.routed and routing_id:
            self.socket.connect_routing_id = routing_id
        self.socket.connect(endpoint)
        self._mode = SocketMode.CONNECT
        self.endpoints.append(endpoint)
        return session
    def disconnect(self, endpoint: ZMQAddress=None) -> None:
        """Disconnect from a remote socket (undoes a call to `connect()`).

        Important:
            Does not discards sessions that are bound to any disconnected endpoint.
            Use :meth:`discard_session` to disconnect & discard associated session.

        Arguments:
            endpoint: Endpoint address or None to disconnect from all connected endpoints.
                      Note: The address must be the same as the addresss returned by
                      :meth:`connect`.

        Raises:
            ChannelError: If channel is not connected to specified `endpoint`.
        """
        assert self.socket is not None
        assert self.mode == SocketMode.CONNECT
        if endpoint and endpoint not in self.endpoints:
            raise ChannelError(f"Endpoint '{endpoint}' not openned")
        addrs = [endpoint] if endpoint else list(self.endpoints)
        for addr in addrs:
            self.socket.disconnect(addr)
            self.endpoints.remove(addr)
        if not self.endpoints:
            self._mode = SocketMode.UNKNOWN
    def can_send(self, timeout: int=0) -> bool:
        """Returns True if underlying ZMQ socket is ready to accept at least one outgoing
        message without blocking (or dropping it).

        Important:
            It may return True for some sockets although subsequent `send()` may fail or
            block. Typicall situation is ROUTER socket that is attached to multiple peers.

        Arguments:
            timeout: Timeout in milliseconds passed to socket poll() call.
        """
        return self.socket.poll(timeout, POLLOUT) == POLLOUT
    def message_available(self, timeout: int=0) -> bool:
        """Returns True if underlying ZMQ socket is ready to receive at least one message
        without blocking (or error).

        Arguments:
            timeout: Timeout in milliseconds passed to socket poll() call.
        """
        return self.socket.poll(timeout, POLLIN) == POLLIN
    def send(self, msg: Message, session: Session) -> int:
        """Sends protocol message.

        Arguments:
            msg: Message to be sent.
            session: Session to which the message belongs.

        Returns:
            Zero for success, or ZMQ error code.
        """
        result = 0
        zmsg = msg.as_zmsg()
        if self.routed:
            zmsg.insert(0, session.routing_id)
        try:
            self.send_zmsg(zmsg)
        except Again as exc:
            if self.on_send_later.is_set() and self.on_send_later(self, session, msg):
                result = 0
            else:
                result = exc.errno
        except ZMQError as exc:
            if self.on_send_failed.is_set() and self.on_send_failed(self, session, msg, exc.errno):
                result = 0
            else:
                result = exc.errno
        return result
    def send_zmsg(self, zmsg: TZMQMessage) -> None:
        """Sends ZMQ multipart message.

        Important:
            Does not handle any ZMQError exception.
        """
        assert self.socket is not None
        assert Direction.OUT in self.direction, "Call to send() on RECEIVE-only channel"
        self.socket.send_multipart(zmsg)
    def receive(self, timeout: int=None) -> Any:
        """Receive and process protocol message with assigned protocol.

        If protocol raises `InvalidMessageError` on message conversion, it calls
        `Protocol.on_invalid_msg` event handler (if defined) before message is dropped.
        Exceptions raised by event handler are ignored, only `RuntimeWarning` is emitted.

        If there no session is found route, it first calls `Protocol.accept_new_session()`,
        and message is handled only when new session is accepted.

        Arguments:
             timeout: The timeout (in milliseconds) to wait for message.

        Returns:
            Whatever protocol message handler returns, sentinel TIMEOUT when timeout
            expires, or sentinel INVALID when:
            a) received message was not valid protocol message, or b) handler raises
            an exception, or c) there is no session associated with peer and new session
            was not accepted by protocol.
        """
        if timeout is not None:
            if self.socket.poll(timeout, POLLIN) == 0:
                return TIMEOUT
        try:
            zmsg = self.receive_zmsg()
        except Again as exc:
            if not (self.on_receive_later.is_set() and self.on_receive_later(self)):
                raise
            else:
                return INVALID
        except ZMQError as exc:
            if not (self.on_receive_failed.is_set() and self.on_receive_failed(self, exc.errno)):
                raise
            else:
                return INVALID
        routing_id: RoutingID = zmsg.pop(0) if self.routed else INTERNAL_ROUTE
        session = self.sessions.get(routing_id)
        #
        try:
            msg = self._protocol.convert_msg(zmsg)
        except InvalidMessageError as exc:
            try:
                self._protocol.handle_invalid_msg(self, session, exc)
            except:
                warnings.warn('Exception raised in invalid message handler', RuntimeWarning)
            return INVALID
        #
        if session is None:
            # This is the first message received for transmission with this peer
            if not self._protocol.accept_new_session(self, routing_id, msg):
                return INVALID
            session = self.create_session(routing_id)
        #
        return self._protocol.handle_msg(self, session, msg)
    def receive_zmsg(self) -> TZMQMessage:
        """Receive ZMQ multipart message.
        """
        assert self.socket is not None
        assert Direction.IN in self.direction, "Call to receive() on SEND-only channel"
        return self.socket.recv_multipart()
    def is_active(self) -> bool:
        """Returns True if channel is active (binded or connected).
        """
        return bool(self.endpoints)
    def set_wait_in(self, value: bool) -> None:
        "Set/clear `Direction.IN` in `.wait_for`"
        if value:
            self.wait_for |= Direction.IN
        else:
            self.wait_for = (self.wait_for | Direction.IN) ^ Direction.IN
    def set_wait_out(self, value: bool, session: Session=None) -> None:
        """Set/clear `Direction.OUT` in `.wait_for`.

        Arguments:
            value: New value for wait_for_out flag.
            session: Related session.

        Raises:
            ChannelError: For routed channel with active sessions when session is not provided.

        Important:
            If channel has active sessions, the `Session.send_pending` flag is also altered.
        """
        if session is None and self.sessions:
            if self.routed:
                raise ChannelError("Session required for routed channel")
            session = self.session
        if value:
            self.wait_for |= Direction.OUT
        else:
            self.wait_for = (self.wait_for | Direction.OUT) ^ Direction.OUT
        if session is not None:
            session.send_pending = value
    def wait(self, timeout: int=None) -> Direction:
        """Wait for socket events specified by :attr:`wait_for`.

        Arguments:
            timeout: The timeout (in milliseconds) to wait for an event. If unspecified,
                     will wait forever for an event.
        """
        assert self.socket is not None
        return Direction(self.socket.poll(timeout, self._wait_for.value))
    @property
    def name(self) -> str:
        "Channel name."
        return self._name
    @property
    def socket_type(self) -> SocketType:
        "ZMQ socket type this channel uses."
        return self._socket_type
    @property
    def direction(self) -> Direction:
        "Possible directions of transmission over this channel."
        return self._direction
    @property
    def mode(self) -> SocketMode:
        "ZMQ Socket mode."
        return self._mode
    @property
    def manager(self) -> ChannelManager:
        "The channel manager to which this channel belongs."
        return self._mngr
    @property
    def routing_id(self) -> RoutingID:
        """Routing_id value for ZMQ socket.
        """
        return self._routing_id
    @routing_id.setter
    def routing_id(self, value) -> None:
        if self.is_active():
            raise ChannelError("Cannot set routing_id of active channel")
        self._routing_id = value
        if self.socket is not None:
            self.socket.routing_id = value
    @property
    def protocol(self) -> Protocol:
        "Protocol used by channel"
        return self._protocol
    @property
    def session(self) -> Session:
        """Session associated with channel.

        Important: Valid *only* when channel has exactly one associated session.
        """
        assert len(self.sessions) == 1
        return self.sessions[INTERNAL_ROUTE]
    @property
    def snd_timeout(self) -> int:
        "Timeout for send operations."
        return self._snd_timeout
    @snd_timeout.setter
    def snd_timeout(self, value: int) -> None:
        self.socket.sndtimeo = value
        self._snd_timeout = value
    @property
    def rcv_timeout(self) -> int:
        "Timeout for receive operations."
        return self._rcv_timeout
    @rcv_timeout.setter
    def rcv_timeout(self, value: int) -> None:
        self.socket.rcvtimeo = value
        self._rcv_timeout = value
    @property
    def wait_for(self) -> Direction:
        """Direction(s) of transmission events for this channel processed by
        `ChannelManager.wait()` or `Channel.wait()`.

        Raises:
            ChannelError: When assigned value contains direction not supported by channel
                          for transmission.
        """
        return self._wait_for
    @wait_for.setter
    def wait_for(self, value: Direction) -> None:
        if not value in self.direction:
            raise ChannelError("Cannot wait for events in direction not supported "
                               "by channel for transmission.")
        self._wait_for = value
        self._mngr.update_poller(self, value)
    @property
    def logging_id(self) -> str:
        "Returns _logging_id_ or <class_name>[<name>]"
        return getattr(self, '_logging_id_', f'{self.__class__.__name__}[{self.name}]')
    @property
    def log_context(self) -> Any:
        "Logging context. Returns `log_context` from ChannelManager."
        return self._mngr.log_context
    @eventsocket
    def on_output_ready(self, channel: Channel) -> None:
        """Event called when channel is ready to accept at least one outgoing message
        without blocking (or dropping it).

        Arguments:
            channel: Channel ready for sending a message.
        """
    @eventsocket
    def on_shutdown(self, channel: Channel, forced: bool) -> None:
        """Event called by :meth:`ChannelManager.shutdown` before the channel is shut down.

        Important:
            All exceptions escaping this method are silently ignored.

        Arguments:
            channel: Channel to be shut down.
            forced:  When True, the channel will be closed with zero LINGER and all ZMQ
                     errors will be ignored.
        """
    @eventsocket
    def on_send_failed(self, channel: Channel, session: Session, msg: Message, err_code: int) -> bool:
        """Event called by :meth:`Channel.send` when send operation fails with `zmq.ZMQError`
        exception other than EAGAIN.

        If event returns True, the error is ignored, otherwise the error code is reported
        to the caller.
        """
    @eventsocket
    def on_send_later(self, channel: Channel, session: Session, msg: Message) -> bool:
        """Event called by :meth:`Channel.send` when send operation fails with zmq.Again`
        exception.

        If event returns True, the error is ignored, otherwise the error code is reported
        to the caller.
        """
    @eventsocket
    def on_receive_failed(self, channel: Channel, err_code: int) -> bool:
        """Event called by :meth:`Channel.receive` when receive operation fails with
        `zmq.ZMQError` exception other than EAGAIN.

        If event returns True, the receive() returns INVALID, otherwise the exception is
        propagated to the caller.
        """
    @eventsocket
    def on_receive_later(self, channel: Channel) -> bool:
        """Event called by :meth:`Channel.receive` when receive operation fails with
        `zmq.Again` exception.

        If event returns True, the receive() returns INVALID, otherwise the exception is
        propagated to the caller.
        """

# Channels for individual ZMQ socket types
class DealerChannel(Channel):
    """Communication channel over DEALER socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.DEALER

class PushChannel(Channel):
    """Communication channel over PUSH socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.PUSH
        self._direction = Direction.OUT

class PullChannel(Channel):
    """Communication channel over PULL socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.PULL
        self._direction = Direction.IN

class PubChannel(Channel):
    """Communication channel over PUB socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.PUB
        self._direction = Direction.OUT

class SubChannel(Channel):
    """Communication channel over SUB socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.SUB
        self._direction = Direction.IN
    def subscribe(self, topic: bytes):
        """Subscribe to topic.

        Arguments:
            topic: ZMQ topic.
        """
        self.socket.subscribe = topic
    def unsubscribe(self, topic: bytes):
        """Unsubscribe from topic.

        Arguments:
            topic: ZMQ topic.
        """
        self.socket.unsubscribe = topic

class XPubChannel(Channel):
    """Communication channel over XPUB socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.XPUB
    def _configure(self):
        "Create XPUB socket for this channel."
        super()._configure()
        self.socket.xpub_verboser = 1 # pass subscribe and unsubscribe messages on XPUB socket

class XSubChannel(Channel):
    """Communication channel over XSUB socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.XSUB
        self._direction = Direction.IN
    def subscribe(self, topic: bytes):
        """Subscribe to topic.

        Arguments:
            topic: ZMQ topic.
        """
        self.socket.send_multipart(b'\x01', topic)
    def unsubscribe(self, topic: bytes):
        """Unsubscribe to topic.

        Arguments:
            topic: ZMQ topic.
        """
        self.socket.send_multipart(b'\x00', topic)

class PairChannel(Channel):
    """Communication channel over PAIR socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.PAIR

class RouterChannel(Channel):
    """Communication channel over ROUTER socket.
    """
    def _adjust(self):
        self._socket_type = SocketType.ROUTER
        self.routed = True
    def _configure(self):
        super()._configure()
        self.socket.router_mandatory = 1


# Types
TZMQMessage = List[Union[bytes, Frame]]
"ZMQ multipart message"
TMessageFactory = Callable[[Optional[TZMQMessage]], Message]
"Message factory callable"
TSocketOptions = Dict[str, Any]
"ZMQ socket options"
TMessageHandler = Callable[[Channel, Session, Message], None]
"Message handler"
