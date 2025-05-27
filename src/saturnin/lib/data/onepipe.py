#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/data/onepipe.py
# DESCRIPTION:    Base class for Saturnin data provider and consumer microservices
# CREATED:        14.12.2020
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

"""Saturnin base classes for data provider and consumer microservices using the FBDP protocol.

This module provides abstract base classes (`BaseDataPipeMicro`, `DataProviderMicro`,
`DataConsumerMicro`) and their associated configurations (`BaseDataPipeConfig`,
`DataProviderConfig`, `DataConsumerConfig`) to simplify the creation of
microservices that act as either producers or consumers of data over a
Saturnin data pipe. These classes handle much of the common boilerplate
for FBDP communication, allowing developers to focus on the specific
data handling logic.
"""

from __future__ import annotations

import uuid
from functools import partial
from typing import Final, cast

import zmq
from saturnin.base import (
    MIME,
    Channel,
    ComponentConfig,
    DealerChannel,
    Direction,
    Error,
    Message,
    Outcome,
    PipeSocket,
    ServiceDescriptor,
    Session,
    SocketMode,
    StopError,
    ZMQAddress,
)
from saturnin.component.micro import MicroService
from saturnin.protocol.fbdp import ErrorCode, FBDPClient, FBDPMessage, FBDPServer, FBDPSession

from firebird.base.config import BoolOption, EnumOption, IntOption, MIMEOption, StrOption, ZMQAddressOption

#: Channel & endpoint name
PIPE_CHN: Final[str] = 'pipe'

class BaseDataPipeConfig(ComponentConfig):
    """Base data provider/consumer microservice configuration.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: Stop service when pipe is closed
        self.stop_on_close: BoolOption = \
            BoolOption('stop_on_close', "Stop service when pipe is closed", default=True)
        #: Data Pipe Identification
        self.pipe: StrOption = \
            StrOption('pipe', "Data Pipe Identification", required=True)
        #: Data Pipe endpoint address
        self.pipe_address: ZMQAddressOption = \
            ZMQAddressOption('pipe_address', "Data Pipe endpoint address", required=True)
        #: Data Pipe Mode
        self.pipe_mode: EnumOption = \
            EnumOption('pipe_mode', SocketMode, "Data Pipe Mode", required=True)
        #: Pipe data format specification
        self.pipe_format: MIMEOption = \
            MIMEOption('pipe_format', "Pipe data format specification")
        #: Data batch size
        self.batch_size: IntOption = \
            IntOption('batch_size', "Data batch size", required=True, default=50)
        #: READY message schedule interval in milliseconds
        self.ready_schedule_interval: IntOption = \
            IntOption('ready_schedule_interval',
                      "READY message schedule interval in milliseconds", required=True,
                      default=1000)
    def validate(self) -> None:
        """Extended validation.

        - `pipe_format` is required for CONNECT `pipe_mode`.
        """
        super().validate()
        if self.pipe_mode.value is SocketMode.CONNECT and self.pipe_format.value is None:
            raise Error("'pipe_format' required for CONNECT pipe mode.")

class DataProviderConfig(BaseDataPipeConfig):
    """Base data provider microservice configuration.
    """

class DataConsumerConfig(BaseDataPipeConfig):
    """Base data consumer microservice configuration.
    """

class BaseDataPipeMicro(MicroService):
    """Base data provider/consumer microservice.

    Abstract base class for both providers and consumers. It handles the common FBDP logic.

    Descendant classes should override:

    - `handle_accept_client` to validate client request and acquire resources associated
      with the pipe.
    - `handle_produce_data` to produce data for outgoing DATA message (PRODUCER only).
    - `handle_accept_data` to process received data (CONSUMER only).
    - `handle_pipe_closed` to release resources associated with the pipe.

    Arguments:
        zmq_context: ZeroMQ Context.
        descriptor: Service descriptor.
        peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
    """
    def __init__(self, zmq_context: zmq.Context, descriptor: ServiceDescriptor, *,
                 peer_uid: uuid.UUID | None=None):
        super().__init__(zmq_context, descriptor, peer_uid=peer_uid)
        #: Pipe socket this service handles if operated as server (bind). Must be set
        #: in descendant class.
        #: For PROVIDER it's `.PipeSocket.OUTPUT`, for CONSUMER it's `.PipeSocket.INPUT`
        self.server_socket: PipeSocket = None
        #: FDBP protocol handler (server or client)
        #: This object manages the FBDP state machine and message handling.
        self.protocol: FBDPServer | FBDPClient = None
        # Next members are set in initialize()
        #: [Configuration] Whether service should stop when pipe is closed
        self.stop_on_close: bool = None
        #: [Configuration] Data Pipe Identification
        self.pipe: str = None
        #: [Configuration] Data Pipe Mode
        self.pipe_mode: SocketMode = None
        #: [Configuration] Data Pipe endpoint address
        self.pipe_address: ZMQAddress = None
        #: [Configuration] Pipe data format specification
        self.pipe_format: MIME = None
        #: [Configuration] Data batch size
        self.batch_size: int = None
        #: [Configuration] READY message schedule interval in milliseconds
        self.ready_schedule_interval: int = None
    def initialize(self, config: BaseDataPipeConfig) -> None:
        """Verify configuration and assemble component structural parts.

        - Sets up the service based on the provided configuration.
        - Creates the appropriate FBDP protocol handler (`FBDPServer` for `BIND`,
          `FBDPClient` for `CONNECT`).
        - Registers default event handlers for various FBDP events (e.g., `on_accept_client`,
          `on_pipe_closed`, `on_produce_data`, `on_accept_data`).
        - Creates a `DealerChannel` for communication over the pipe.
        """
        super().initialize(config)
        # Configuration
        self.stop_on_close = config.stop_on_close.value
        self.pipe: str = config.pipe.value
        self.pipe_mode: SocketMode = config.pipe_mode.value
        self.pipe_address: ZMQAddress = config.pipe_address.value
        self.pipe_format: MIME | None = config.pipe_format.value
        self.batch_size: int = config.batch_size.value
        self.ready_schedule_interval: int = config.ready_schedule_interval.value
        # Set up FBDP protocol
        if self.pipe_mode == SocketMode.BIND:
            # server
            self.protocol = FBDPServer()
            self.protocol.on_exception = self.handle_exception
            self.protocol.on_accept_client = self.handle_accept_client
            self.protocol.on_schedule_ready = self.handle_schedule_ready
            # We have an endpoint to bind
            self.endpoints[PIPE_CHN] = [self.pipe_address]
        else:
            # client
            self.protocol = FBDPClient()
        # common parts
        self.protocol.batch_size = self.batch_size
        self.protocol.on_pipe_closed = self.handle_pipe_closed
        self.protocol.on_produce_data = self.handle_produce_data
        self.protocol.on_accept_data = self.handle_accept_data
        # Create pipe channel
        self.mngr.create_channel(DealerChannel, PIPE_CHN, self.protocol, wait_for=Direction.IN)
    def aquire_resources(self) -> None:
        """Acquire resources required by the component.

        Specifically:

           If `.pipe_mode` is `~SocketMode.CONNECT`, it connects to the data pipe
           endpoint and initiates the FBDP `OPEN` handshake. The client socket type
           (INPUT/OUTPUT) is determined as the inverse of `.server_socket`.
        """
        # Connect to the data pipe
        if self.pipe_mode == SocketMode.CONNECT:
            chn: Channel = self.mngr.channels[PIPE_CHN]
            session = chn.connect(self.pipe_address)
            # OPEN the data pipe connection, this also fills session attributes
            # PRODUCER client must attach to INPUT, CONSUMER client must attach to OUTPUT
            client_socket = PipeSocket.INPUT if self.server_socket is PipeSocket.OUTPUT \
                else PipeSocket.OUTPUT
            cast(FBDPClient, chn.protocol).send_open(chn, session, self.pipe,
                                                     client_socket, self.pipe_format)
    def release_resources(self) -> None:
        """Release resources aquired by component:

        Specifically:

           Sends an FBDP `CLOSE` message (indicating an error) to all active pipe sessions.
        """
        # CLOSE all active data pipe sessions
        chn: Channel = self.mngr.channels[PIPE_CHN]
        # send_close() will discard session, so we can't iterate over sessions.values() directly
        for session in list(chn.sessions.values()):
            # We have to report error here, because normal is to close pipes before
            # shutdown is commenced. Mind that service shutdown could be also caused by error!
            cast(FBDPServer, chn.protocol).send_close(chn, session, ErrorCode.ERROR)
    def handle_exception(self, channel: Channel, session: Session, msg: Message,
                         exc: Exception) -> None:
        """Event handler called by `.handle_msg()` on exception in message handler.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with connection.
            msg:     Message.
            exc:     Exception.

        Sets service outcome to ERROR and notes exception as details.
        """
        self.outcome = Outcome.ERROR
        self.details = exc
    # FBDP server only
    def handle_accept_client(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed when client connects to the data pipe via OPEN message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The session attributes `~.FBDPSession.pipe`, `~.FBDPSession.socket`,
        `~.FBDPSession.data_format` and `~.FBDPSession.params` contain information sent by
        client, and the event handler validates the request.

        If request should be rejected, it raises the `.StopError` exception with `~Error.code`
        attribute containing the `~saturnin.protocol.fbdp.ErrorCode` to be returned in
        CLOSE message.

        Important:
            Base implementation validates pipe identification and pipe socket, and converts
            data format from string to MIME (in session).

            The descendant class that overrides this method must call `super` as first
            action.
        """

        if session.pipe != self.pipe:
            raise StopError(f"Unknown data pipe '{session.pipe}'",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We're server, so clients can only attach to our server_socket
        if session.socket is not self.server_socket:
            raise StopError(f"'{session.socket}' socket not available",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We work with MIME formats, so we'll convert the format specification to MIME
        session.data_format = MIME(session.data_format)
    def handle_schedule_ready(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed in order to send the READY message to the client later.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The event handler may cancel the transmission by raising the `.StopError` exception
        with `~Error.code` attribute containing the `~saturnin.protocol.fbdp.ErrorCode` to be
        returned in CLOSE message.

        Important:
            The base implementation schedules `~.FBDPServer.resend_ready()` according to
            `.ready_schedule_interval` configuration option.
        """
        self.schedule(partial(cast(FBDPServer, channel.protocol).resend_ready,
                              channel, session),
                      self.ready_schedule_interval)
    # FBDP common
    def handle_produce_data(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Event handler executed to store data into outgoing DATA message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
            msg: DATA message that will be sent to client.

        The event handler must store the data in `msg.data_frame` attribute. It may also
        set ACK-REQUEST flag and `type_data` attribute.

        The event handler may cancel the transmission by raising the `.StopError` exception
        with `code` attribute containing the `~saturnin.protocol.fbdp.ErrorCode` to be
        returned in CLOSE message.

        Note:
            To indicate end of data, raise StopError with ErrorCode.OK code.

            Exceptions are handled by protocol, but only StopError is checked for protocol
            ErrorCode. As we want to report INVALID_DATA properly, we have to convert
            UnicodeError into StopError.

        Important:
            The base implementation simply raises `.StopError` with `ErrorCode.OK` code,
            so the descendant class must override this method without `super` call.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_accept_data(self, channel: Channel, session: FBDPSession, data: bytes) -> None:
        """Event handler executed to process data received in DATA message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
            data: Data received from client.

        The event handler may cancel the transmission by raising the `.StopError` exception
        with `~Error.code` attribute containing the `~saturnin.protocol.fbdp.ErrorCode` to
        be returned in CLOSE message.

        Note:
            The ACK-REQUEST in received DATA message is handled automatically by protocol.

        Important:
            The base implementation simply raises `.StopError` with `ErrorCode.OK` code,
            so the descendant class must override this method without `super` call.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_pipe_closed(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                           exc: Exception | None=None) -> None:
        """Event handler executed when CLOSE message is received or sent, to release any
        resources associated with current transmission.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            msg: Received/sent CLOSE message.
            exc: Exception that caused the error.

        Important:
            The base implementation does only two actions:

            - If exception is provided, sets service execution outcome to ERROR
              and notes exception in details.
            - Stops the service if `.stop_on_close` is True.

            The descendant class that overrides this method must call `super`.
        """
        # FDBP converts exceptions raised in our event handler to CLOSE messages, so
        # here is the central place to handle errors in data pipe processing.
        # Note problem in service execution outcome
        if exc is not None:
            self.outcome = Outcome.ERROR
            self.details = exc
        #
        if self.stop_on_close:
            self.stop.set()

class DataProviderMicro(BaseDataPipeMicro):
    """Base data provider microservice (PRODUCER).

    This class specializes `BaseDataPipeMicro` for services that produce data
    and send it over an FBDP pipe.

    Descendant classes should override:

    - `~.BaseDataPipeMicro.handle_accept_client` to validate client requests and acquire
      resources associated with the pipe.
    - `~.BaseDataPipeMicro.handle_produce_data` to generate and provide the data for
      outgoing `DATA` messages.
    - `~.BaseDataPipeMicro.handle_pipe_closed` to release resources associated with the pipe.
    """
    def initialize(self, config: DataProviderConfig) -> None:
        """Verify configuration and assemble component structural parts.
        """
        super().initialize(config)
        self.server_socket = PipeSocket.OUTPUT
        # High water mark optimization
        chn: Channel = self.mngr.channels[PIPE_CHN]
        chn.sock_opts['rcvhwm'] = 5
        chn.sock_opts['sndhwm'] = int(self.batch_size / 2) + 5

class DataConsumerMicro(BaseDataPipeMicro):
    """Base data provider microservice.

    Descendant classes should override:

    - `~.BaseDataPipeMicro.handle_accept_client` to validate client request and aquire
      resources associated with pipe.
    - `~.BaseDataPipeMicro.handle_accept_data` to process received data.
    - `~.BaseDataPipeMicro.handle_pipe_closed` to release resource assiciated with pipe.
    """
    def initialize(self, config: DataConsumerConfig) -> None:
        """Verify configuration and assemble component structural parts.
        """
        super().initialize(config)
        self.server_socket = PipeSocket.INPUT
        # High water mark optimization
        chn: Channel = self.mngr.channels[PIPE_CHN]
        chn.sock_opts['rcvhwm'] = int(self.batch_size / 2) + 5
        chn.sock_opts['sndhwm'] = 5
