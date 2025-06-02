#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/data/filter.py
# DESCRIPTION:    Base class for Saturnin data filter microservices
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

"""Saturnin base class for data filter microservices.

This module provides `DataFilterMicro` and its configuration `DataFilterConfig`,
designed for microservices that read data from an input FBDP data pipe,
process or transform it, and then write the results to an output FBDP
data pipe. It manages the complexities of handling two concurrent pipe
connections and synchronizing data flow between them.
"""

from __future__ import annotations

import uuid
from collections import deque
from functools import partial
from typing import Any, Final, cast

import zmq
from saturnin.base import (
    ANY,
    MIME,
    Channel,
    ComponentConfig,
    DealerChannel,
    Direction,
    Error,
    Message,
    Outcome,
    PipeSocket,
    Protocol,
    PullChannel,
    PushChannel,
    ServiceDescriptor,
    Session,
    SimpleMessage,
    SocketMode,
    StopError,
    ZMQAddress,
)
from saturnin.component.micro import MicroService
from saturnin.protocol.fbdp import ErrorCode, FBDPClient, FBDPMessage, FBDPServer, FBDPSession

from firebird.base.config import BoolOption, EnumOption, IntOption, MIMEOption, StrOption, ZMQAddressOption

#: Pipe INPUT channel & endpoint name
INPUT_PIPE_CHN: Final[str] = 'input-pipe'
#: Pipe OUTPUT channel & endpoint name
OUTPUT_PIPE_CHN: Final[str] = 'output-pipe'
#: Wake PUSH channel & endpoint name
WAKE_PUSH_CHN: Final[str] = 'wake-push'
#: Wake PULL channel & endpoint name
WAKE_PULL_CHN: Final[str] = 'wake-pull'

class DataFilterConfig(ComponentConfig):
    """Configuration for data filter microservices.

    This class defines settings specific to microservices that operate as data filters,
    managing an input pipe and an output pipe.

    Arguments:
       name: Configuration section name for this component.
    """
    def __init__(self, name: str):
        super().__init__(name)
        #: When input pipe is closed with error, close output with error as well
        self.propagate_input_error: BoolOption = \
            BoolOption('propagate_input_error',
                       "When input pipe is closed with error, close output with error as well",
                       default=True)
        # Input pipe
        #: Input Data Pipe Identification
        self.input_pipe: StrOption = \
            StrOption('input_pipe', "Input Data Pipe Identification", required=True)
        #: Input Data Pipe endpoint address
        self.input_pipe_address: ZMQAddressOption = \
            ZMQAddressOption('input_pipe_address', "Input Data Pipe endpoint address", required=True)
        #: Input Data Pipe Mode
        self.input_pipe_mode: EnumOption = \
            EnumOption('input_pipe_mode', SocketMode, "Input Data Pipe Mode", required=True)
        #: Input Pipe data format specification
        self.input_pipe_format: MIMEOption = \
            MIMEOption('input_pipe_format', "Input Pipe data format specification")
        #: Input Pipe Data batch size
        self.input_batch_size: IntOption = \
            IntOption('input_batch_size', "Input Pipe Data batch size", required=True, default=50)
        #: Input Pipe READY message schedule interval in milliseconds
        self.input_ready_schedule_interval: IntOption = \
            IntOption('input_ready_schedule_interval',
                      "Input Pipe READY message schedule interval in milliseconds",
                      required=True, default=1000)
        # Output pipe
        #: Output Data Pipe Identification
        self.output_pipe: StrOption = \
            StrOption('output_pipe', "Output Data Pipe Identification", required=True)
        #: Output Data Pipe endpoint address
        self.output_pipe_address: ZMQAddressOption = \
            ZMQAddressOption('output_pipe_address', "Output Data Pipe endpoint address", required=True)
        #: Output Data Pipe Mode
        self.output_pipe_mode: EnumOption = \
            EnumOption('output_pipe_mode', SocketMode, "Output Data Pipe Mode", required=True)
        #: Output Pipe data format specification
        self.output_pipe_format: MIMEOption = \
            MIMEOption('output_pipe_format', "Output Pipe data format specification")
        #: Output Pipe Data batch size
        self.output_batch_size: IntOption = \
            IntOption('output_batch_size', "Output Pipe Data batch size", required=True, default=50)
        #: Output Pipe READY message schedule interval in milliseconds
        self.output_ready_schedule_interval: IntOption = \
            IntOption('output_ready_schedule_interval',
                      "Output Pipe READY message schedule interval in milliseconds", required=True,
                      default=1000)
    def validate(self) -> None:
        """Extended validation.

        Ensures that:

        - `input_pipe_format` is specified if `input_pipe_mode` is `CONNECT`.
        - `output_pipe_format` is specified if `output_pipe_mode` is `CONNECT`.
        """
        super().validate()
        if self.input_pipe_mode.value is SocketMode.CONNECT and self.input_pipe_format.value is None:
            raise Error("'input_pipe_format' required for CONNECT pipe mode.")
        if self.output_pipe_mode.value is SocketMode.CONNECT and self.output_pipe_format.value is None:
            raise Error("'output_pipe_format' required for CONNECT pipe mode.")

class DataFilterMicro(MicroService):
    """"Base class for data filter microservices.

    This microservice reads data from an input pipe, processes it, and writes
    the results to an output pipe. It manages two FBDP connections and uses
    an internal "wake" mechanism to signal data availability for the output pipe.

    Descendant classes should override:

    - `.handle_input_accept_client` to validate client requests and acquire resources
      associated with the input pipe.
    - `.handle_output_accept_client` to validate client requests and acquire resources
      associated with the output pipe.
    - `.handle_output_produce_data` to provide the processed data for outgoing `DATA`
      messages on the output pipe.
    - `.handle_input_accept_data` to process data received from the input pipe.
    - `.handle_input_pipe_closed` to release resources associated with the input pipe.
    - `.handle_output_pipe_closed` to release resources associated with the output pipe.

    Arguments:
        zmq_context: ZeroMQ Context.
        descriptor: Service descriptor.
        peer_uid: Peer ID, `None` means that newly generated UUID type 1 should be used.
    """
    def __init__(self, zmq_context: zmq.Context, descriptor: ServiceDescriptor, *,
                 peer_uid: uuid.UUID | None=None):
        super().__init__(zmq_context, descriptor, peer_uid=peer_uid)
        self.outcome = Outcome.UNKNOWN
        self.details = None
        #: Internal deque to buffer data processed from the input pipe, pending transmission
        #: on the output pipe.
        self.output: deque = deque()
        # Next members are set in initialize()
        #: Closing flag
        self.closing: bool = False
        #: [Configuration] When input pipe is closed with error, close output with error as well
        self.propagate_input_error: bool = None
        #: [Configuration] Data Pipe Identification
        self.input_pipe: str = None
        #: [Configuration] Data Pipe Mode
        self.input_pipe_mode: SocketMode = None
        #: [Configuration] Data Pipe endpoint address
        self.input_pipe_address: ZMQAddress = None
        #: [Configuration] Pipe data format specification
        self.input_pipe_format: MIME = None
        #: [Configuration] Data batch size
        self.input_batch_size: int = None
        #: [Configuration] pipe READY message schedule interval in milliseconds
        self.input_ready_schedule_interval: int = None
        #: FDBP protocol handler (server or client) for input pipe
        self.input_protocol: FBDPServer | FBDPClient = None
        #: Input pipe channel
        self.pipe_in_chn: Channel = None
        #: [Configuration] Data Pipe Identification
        self.output_pipe: str = None
        #: [Configuration] Data Pipe Mode
        self.output_pipe_mode: SocketMode = None
        #: [Configuration] Data Pipe endpoint address
        self.output_pipe_address: ZMQAddress = None
        #: [Configuration] Pipe data format specification
        self.output_pipe_format: MIME = None
        #: [Configuration] Data batch size
        self.output_batch_size: int = None
        #: [Configuration] pipe READY message schedule interval in milliseconds
        self.output_ready_schedule_interval: int = None
        #: FDBP protocol handler (server or client) for output pipe
        self.output_protocol: FBDPServer | FBDPClient = None
        #: Output pipe channel
        self.pipe_out_chn: Channel = None
        #: Internal AWAKE address
        self.wake_address: ZMQAddress = None
        #: Internal AWAKE output channel
        self.wake_out_chn: PushChannel = None
        #: Internal AWAKE input channel
        self.wake_in_chn: PullChannel = None
    def initialize(self, config: DataFilterConfig) -> None:
        """Verify configuration and assemble component structural parts.

        Arguments:
          config: Service configuration
        """
        super().initialize(config)
        self.closing = False
        # Configuration
        self.propagate_input_error = config.propagate_input_error.value
        # INPUT pipe
        self.input_pipe = config.input_pipe.value
        self.input_pipe_mode = config.input_pipe_mode.value
        self.input_pipe_address = config.input_pipe_address.value
        self.input_pipe_format = config.input_pipe_format.value
        self.input_batch_size = config.input_batch_size.value
        self.input_ready_schedule_interval = config.input_ready_schedule_interval.value
        # Set up FBDP protocol
        if self.input_pipe_mode == SocketMode.BIND:
            # server
            self.input_protocol = FBDPServer()
            self.input_protocol.on_exception = self.handle_exception
            self.input_protocol.on_accept_client = self.handle_input_accept_client
            self.input_protocol.on_schedule_ready = self.handle_input_schedule_ready
            # We have an endpoint to bind
            self.endpoints[INPUT_PIPE_CHN] = [self.input_pipe_address]
        else:
            # client
            self.input_protocol = FBDPClient()
        # common parts
        self.input_protocol.batch_size = self.input_batch_size
        self.input_protocol.on_pipe_closed = self.handle_input_pipe_closed
        self.input_protocol.on_accept_data = self.handle_input_accept_data
        self.input_protocol.on_get_data = self.handle_input_get_data
        # Create INPUT pipe channel
        self.pipe_in_chn = self.mngr.create_channel(DealerChannel, INPUT_PIPE_CHN,
                                                    self.input_protocol,
                                                    wait_for=Direction.IN)
        # OUTPUT pipe
        self.output_pipe = config.output_pipe.value
        self.output_pipe_mode = config.output_pipe_mode.value
        self.output_pipe_address = config.output_pipe_address.value
        self.output_pipe_format = config.output_pipe_format.value
        self.output_batch_size = config.output_batch_size.value
        self.output_ready_schedule_interval = config.output_ready_schedule_interval.value
        # Set up FBDP protocol
        if self.output_pipe_mode == SocketMode.BIND:
            # server
            self.output_protocol = FBDPServer()
            self.output_protocol.on_exception = self.handle_exception
            self.output_protocol.on_accept_client = self.handle_output_accept_client
            self.output_protocol.on_schedule_ready = self.handle_output_schedule_ready
            # We have an endpoint to bind
            self.endpoints[OUTPUT_PIPE_CHN] = [self.output_pipe_address]
        else:
            # client
            self.output_protocol = FBDPClient()
        # common parts
        self.output_protocol.batch_size = self.output_batch_size
        self.output_protocol.on_pipe_closed = self.handle_output_pipe_closed
        self.output_protocol.on_produce_data = self.handle_output_produce_data
        self.output_protocol.on_get_data = self.handle_output_get_data
        # Create OUTPUT pipe channel
        self.pipe_out_chn = self.mngr.create_channel(DealerChannel, OUTPUT_PIPE_CHN,
                                                              self.output_protocol,
                                                              wait_for=Direction.IN)
        # Awake channels
        self.wake_address = ZMQAddress(f'inproc://{self.peer.uid.hex}-wake')
        wake_protocol = Protocol()
        wake_protocol.handlers[ANY] = self.handle_wake_msg
        # PUSH wake
        self.wake_out_chn = self.mngr.create_channel(PushChannel, WAKE_PUSH_CHN,
                                                              wake_protocol)
        # PULL wake
        self.wake_in_chn = self.mngr.create_channel(PullChannel, WAKE_PULL_CHN,
                                                             wake_protocol,
                                                             wait_for=Direction.IN)
        # We have an endpoint to bind
        self.endpoints[WAKE_PULL_CHN] = [self.wake_address]
    def aquire_resources(self) -> None:
        """Acquire resources required by the component.

        This involves:

        1. Connecting the internal "wake" PUSH channel to its PULL counterpart.
        2. If `input_pipe_mode` is `CONNECT`, establishes a connection to the
           input data pipe and initiates the FBDP `OPEN` handshake.
        3. If `output_pipe_mode` is `CONNECT`, establishes a connection to the
           output data pipe and initiates the FBDP `OPEN` handshake.
        """
        # Connect wake PUSH
        self.wake_out_chn.connect(self.wake_address)
        # Connect to the data pipes
        # INPUT pipe
        if self.input_pipe_mode == SocketMode.CONNECT:
            session = self.pipe_in_chn.connect(self.input_pipe_address)
            # OPEN the data pipe connection, this also fills session attributes
            # We are CONSUMER client, we must attach to server OUTPUT
            cast(FBDPClient, self.pipe_in_chn.protocol).send_open(self.pipe_in_chn,
                                                                  session, self.input_pipe,
                                                                  PipeSocket.OUTPUT,
                                                                  self.input_pipe_format)
        # OUTPUT pipe
        if self.output_pipe_mode == SocketMode.CONNECT:
            session = self.pipe_out_chn.connect(self.output_pipe_address)
            # OPEN the data pipe connection, this also fills session attributes
            # We are PRODUCER client, we must attach to server INPUT
            cast(FBDPClient, self.pipe_out_chn.protocol).send_open(self.pipe_out_chn,
                                                                   session, self.output_pipe,
                                                                   PipeSocket.INPUT,
                                                                   self.output_pipe_format)
    def release_resources(self) -> None:
        """Release resources acquired by the component.

        This involves:

        1. Discarding the session for the internal "wake" PUSH channel.
        2. Sending an FBDP `CLOSE` message (indicating an error) to all active
           sessions on the input data pipe.
        3. Sending an FBDP `CLOSE` message (indicating an error) to all active
           sessions on the output data pipe.
        """
        # Disonnect wake PUSH
        for session in list(self.wake_out_chn.sessions.values()):
            self.wake_out_chn.discard_session(session)
        # CLOSE all active data input pipe sessions
        # send_close() will discard session, so we can't iterate over sessions.values() directly
        for session in list(self.pipe_in_chn.sessions.values()):
            # We have to report error here, because normal is to close pipes before
            # shutdown is commenced. Mind that service shutdown could be also caused by error!
            cast(FBDPServer, self.pipe_in_chn.protocol).send_close(self.pipe_in_chn, session, ErrorCode.ERROR)
        # CLOSE all active data output pipe sessions
        # send_close() will discard session, so we can't iterate over sessions.values() directly
        for session in list(self.pipe_out_chn.sessions.values()):
            # We have to report error here, because normal is to close pipes before
            # shutdown is commenced. Mind that service shutdown could be also caused by error!
            cast(FBDPServer, self.pipe_out_chn.protocol).send_close(self.pipe_out_chn,
                                                                    session, ErrorCode.ERROR)
    def store_output(self, data: Any) -> None:
        """Store data to output queue and send wake notification.

        Arguments:
            data: Data to be stored to output queue.
        """
        self.output.append(data)
        msg = SimpleMessage()
        msg.data.append(b'wake')
        self.wake_out_chn.send(msg, self.wake_out_chn.session)
    def store_batch_output(self, batch: list) -> None:
        """Store batch of data to output queue and send wake notification.

        Arguments:
            batch: Data to be stored to output queue.
        """
        for data in batch:
            self.output.append(data)
        if self.output:
            msg = SimpleMessage()
            msg.data.append(b'wake')
            self.wake_out_chn.send(msg, self.wake_out_chn.session)
    def finish_input_processing(self, channel: Channel, session: FBDPSession, code: ErrorCode) -> None:
        """Called when input pipe is closed while output pipe will remain open.

        When code is `ErrorCode.OK`, the input was closed normally. Otherwise it indicates
        the type of problem that caused the input to be closed.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            code:    Input pipe closing ErrorCode.

        Note:
            The default implementation does nothing.
        """
    def handle_wake_msg(self, channel: Channel, session: Session, msg: Message) -> None:
        """Handler for "data available" pings sent via wake channels.

        Arguments:
            channel: Channel associated with wake delivery.
            session: Session associated with client.
            msg: Wake message.
        """
        if not self.output:
            # Unlikely case when we've got wake but all data were already sent
            return
        if not self.pipe_out_chn.sessions:
            # We need active pipe connection
            return
        session: FBDPSession = self.pipe_out_chn.session
        if session.transmit is not None:
            # Transmission in progress, make sure that we will send data
            self.pipe_out_chn.set_wait_out(True, session)
        elif self.output_pipe_mode is SocketMode.BIND and not session.await_ready:
            # We are server without active transmission and READY was not sent yet, so we
            # can send READY immediately
            cast(FBDPServer, self.pipe_out_chn.protocol)._init_new_batch(self.pipe_out_chn,
                                                                         session)
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
        if isinstance(exc, StopError):
            if getattr(exc, 'code', None) is ErrorCode.OK:
                return
        self.outcome = Outcome.ERROR
        self.details = exc
    def handle_input_get_data(self, channel: Channel, session: FBDPSession) -> bool:
        """Event handler executed to query the service whether is ready to accept input data.

        Arguments:
            channel: Channel associated with input data pipe.
            session: Session associated with server.

        Returns True if output pipe is open, otherwise false.
        """
        return bool(self.pipe_in_chn.sessions)
    def handle_output_get_data(self, channel: Channel, session: FBDPSession) -> bool:
        """Event handler executed to query the data source for data availability.

        Arguments:
            channel: Channel associated with output data pipe.
            session: Session associated with connection.

        Returns True if output deque contains any data.

        Cancels the transmission by raising the `.StopError` if there are no output data
        and input pipe is closed.
        """
        have_data = bool(self.output)
        if not have_data and not self.pipe_in_chn.sessions:
            raise StopError("EOF", code=ErrorCode.OK)
        return have_data
    # FBDP server only
    def handle_input_accept_client(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed when client connects to INPUT data pipe via OPEN message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The session attributes `~.FBDPSession.pipe`, `~.FBDPSession.socket`,
        `~.FBDPSession.data_format` and `~.FBDPSession.params` contain information sent by
        client, and the event handler validates the request.

        If request should be rejected, it raises the `.StopError` exception with `code`
        attribute containing the `~saturnin.protocol.fbdp.ErrorCode` to be returned in
        CLOSE message.

        Important:
            Base implementation validates pipe identification and pipe socket, and converts
            data format from string to MIME (in session).

            The descendant class that overrides this method must call `super` as first
            action.
        """
        if session.pipe != self.output_pipe:
            raise StopError(f"Unknown data pipe '{session.pipe}'",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # Clients can attach only to INPUT
        if session.socket is not PipeSocket.INPUT:
            raise StopError(f"'{session.socket}' socket not available",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We work with MIME formats, so we'll convert the format specification to MIME
        session.data_format = MIME(session.data_format)
    def handle_output_accept_client(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed when client connects to OUTPUT data pipe via OPEN message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The session attributes `~.FBDPSession.pipe`, `~.FBDPSession.socket`,
        `~.FBDPSession.data_format` and `~.FBDPSession.params` contain information sent by
        client, and the event handler validates the request.

        If request should be rejected, it raises the `.StopError` exception with `~.Error.code`
        attribute containing the `~saturnin.protocol.fbdp.ErrorCode` to be returned in
        CLOSE message.

        Important:
            Base implementation validates pipe identification and pipe socket, and converts
            data format from string to MIME (in session).

            The descendant class that overrides this method must call `super` as first
            action.
        """
        if session.pipe != self.output_pipe:
            raise StopError(f"Unknown data pipe '{session.pipe}'",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # Clients can attach only to our OUTPUT
        if session.socket is not PipeSocket.OUTPUT:
            raise StopError(f"'{session.socket}' socket not available",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We work with MIME formats, so we'll convert the format specification to MIME
        session.data_format = MIME(session.data_format)
    def handle_input_schedule_ready(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed in order to send the READY message to the client later.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The event handler may cancel the transmission by raising the `.StopError` exception
        with `~.Error.code` attribute containing the `~saturnin.protocol.fbdp.ErrorCode`
        to be returned in CLOSE message.

        Important:
            The base implementation schedules `~.FBDPServer.resend_ready()` according to
            `.input_ready_schedule_interval` configuration option.
        """
        self.schedule(partial(cast(FBDPServer, channel.protocol).resend_ready,
                              channel, session),
                      self.input_ready_schedule_interval)
    def handle_output_schedule_ready(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed in order to send the READY message to the client later.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The event handler may cancel the transmission by raising the `.StopError` exception
        with `~.Error.code` attribute containing the `~saturnin.protocol.fbdp.ErrorCode` to
        be returned in CLOSE message.

        Important:
            The base implementation schedules `~.FBDPServer.resend_ready()` according to
            `.output_ready_schedule_interval` configuration option.
        """
        self.schedule(partial(cast(FBDPServer, channel.protocol).resend_ready,
                              channel, session),
                      self.output_ready_schedule_interval)
    # FBDP common
    def handle_output_produce_data(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Event handler executed to store data into outgoing DATA message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
            msg: DATA message that will be sent to client.

        Important:
            The base implementation simply raises `.StopError` with
            `~saturnin.protocol.fbdp.ErrorCode.OK` code, so the descendant class must
            override this method without `super` call.

            The event handler must `popleft()` data from `.output` queue and store them in
            `msg.data_frame` attribute. It may also set ACK-REQUEST flag and `type_data`
            attribute.

            The event handler may cancel the transmission by raising the `StopError`
            exception with `code` attribute containing the `~saturnin.protocol.fbdp.ErrorCode`
            to be returned in CLOSE message.

        Note:
            To indicate end of data, raise `.StopError` with `~saturnin.protocol.fbdp.ErrorCode.OK` code.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_input_accept_data(self, channel: Channel, session: FBDPSession, data: bytes) -> None:
        """Event handler executed to process data received in DATA message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
            data: Data received from client.

        Important:
            Any output data produced by event handler must be stored into output queue via
            `.store_output()` method.

            The base implementation simply raises `.StopError` with
            `~saturnin.protocol.fbdp.ErrorCode.OK` code, so the descendant class must
            override this method without `super` call.

            The event handler may cancel the transmission by raising the `.StopError`
            exception with `code` attribute containing the `~saturnin.protocol.fbdp.ErrorCode`
            to be returned in CLOSE message.

        Note:
            The ACK-REQUEST in received DATA message is handled automatically by protocol.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_input_pipe_closed(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                                 exc: Exception | None=None) -> None:
        """Event handler executed when CLOSE message is received or sent, to release any
        resources associated with current transmission.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            msg: Received/sent CLOSE message.
            exc: Exception that caused the error.

        Important:
            The base implementation does next actions:

            - If exception is provided, sets service execution outcome to ERROR
              and notes exception in details.
            - Closes the output pipe it's still open  and `.closing` flag is False, and if
              the input is not closed normally and `.propagate_input_error` is True.
            - Sets the signal to stop the service.

            The descendant class that overrides this method must call `super`.
        """
        # FDBP converts exceptions raised in our event handler to CLOSE messages, so
        # here is the central place to handle errors in data pipe processing.
        code: ErrorCode = msg.type_data
        if exc is not None:
            # Note problem in service execution outcome
            if code is not ErrorCode.OK:
                self.outcome = Outcome.ERROR
                self.details = exc
        self.finish_input_processing(channel, session, code)
        # If input is not closed normally and we should propagate the problem, or when
        # there is no data for output, close the output pipe if it's still open
        if (code is not ErrorCode.OK and self.propagate_input_error) or not self.output:
            if not self.closing:
                self.closing = True
                # Sending close discards session, so we shoyuld end with empty session list
                for _session in list(self.pipe_out_chn.sessions.values()):
                    cast(FBDPServer, self.pipe_out_chn.protocol).send_close(self.pipe_out_chn,
                                                                            _session, code, exc)
            # Request service to stop
            self.stop.set()
        self.closing = False
    def handle_output_pipe_closed(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                                  exc: Exception | None=None) -> None:
        """Event handler executed when CLOSE message is received or sent, to release any
        resources associated with current transmission.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with peer.
            msg: Received/sent CLOSE message.
            exc: Exception that caused the error.

        Important:
            The base implementation does next actions:

            - If exception is provided, sets service execution outcome to ERROR
              and notes exception in details.
            - Closes the input pipe if it's still open and `.closing` flag is False.
            - Sets the signal to stop the service.

            The descendant class that overrides this method must call `super`.
        """
        # FDBP converts exceptions raised in our event handler to CLOSE messages, so
        # here is the central place to handle errors in data pipe processing.
        code: ErrorCode = msg.type_data
        if exc is not None:
            # Note problem in service execution outcome
            if code is not ErrorCode.OK:
                self.outcome = Outcome.ERROR
                self.details = exc
        # Close the input pipe if it's still open
        if not self.closing:
            self.closing = True
            for _session in list(self.pipe_in_chn.sessions.values()):
                cast(FBDPServer, self.pipe_in_chn.protocol).send_close(self.pipe_in_chn,
                                                                       _session, code, exc)
        # Request service to stop
        self.stop.set()
        self.closing = False
