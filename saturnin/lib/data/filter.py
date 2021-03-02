#coding:utf-8
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

"""Saturnin base class for data filter microservices
"""

from __future__ import annotations
from typing import Any, List, cast
from functools import partial
from collections import deque
from firebird.base.config import MIME, StrOption, EnumOption, \
     IntOption, BoolOption, ZMQAddressOption, MIMEOption
from saturnin.base import Error, StopError, Direction, SocketMode, PipeSocket, Outcome, \
     ZMQAddress, MIME, ComponentConfig, Message, SimpleMessage, Session, Protocol, Channel, \
     DealerChannel, PushChannel, PullChannel, ANY
from saturnin.component.micro import MicroService
from saturnin.protocol.fbdp import ErrorCode, FBDPServer, FBDPClient, \
     FBDPSession, FBDPMessage

INPUT_PIPE_CHN = 'input-pipe'
OUTPUT_PIPE_CHN = 'output-pipe'
WAKE_PUSH_CHN = 'wake-push'
WAKE_PULL_CHN = 'wake-pull'

class DataFilterConfig(ComponentConfig):
    """Base data provider microservice configuration."""
    def __init__(self, name: str):
        super().__init__(name)
        self.propagate_input_error: BoolOption = \
            BoolOption('propagate_input_error',
                       "When input pipe is closed with error, close output with error as well",
                       default=True)
        # Input pipe
        self.input_pipe: StrOption = \
            StrOption('input_pipe', "Data Pipe Identification", required=True)
        self.input_pipe_address: ZMQAddressOption = \
            ZMQAddressOption('input_pipe_address', "Data Pipe endpoint address", required=True)
        self.input_pipe_mode: EnumOption = \
            EnumOption('input_pipe_mode', SocketMode, "Data Pipe Mode", required=True)
        self.input_pipe_format: MIMEOption = \
            MIMEOption('input_pipe_format', "Pipe data format specification")
        self.input_batch_size: IntOption = \
            IntOption('input_batch_size', "Data batch size", required=True, default=50)
        self.input_ready_schedule_interval: IntOption = \
            IntOption('input_ready_schedule_interval',
                      "READY message schedule interval in milliseconds", required=True,
                      default=1000)
        # Output pipe
        self.output_pipe: StrOption = \
            StrOption('output_pipe', "Data Pipe Identification", required=True)
        self.output_pipe_address: ZMQAddressOption = \
            ZMQAddressOption('output_pipe_address', "Data Pipe endpoint address", required=True)
        self.output_pipe_mode: EnumOption = \
            EnumOption('output_pipe_mode', SocketMode, "Data Pipe Mode", required=True)
        self.output_pipe_format: MIMEOption = \
            MIMEOption('output_pipe_format', "Pipe data format specification")
        self.output_batch_size: IntOption = \
            IntOption('output_batch_size', "Data batch size", required=True, default=50)
        self.output_ready_schedule_interval: IntOption = \
            IntOption('output_ready_schedule_interval',
                      "READY message schedule interval in milliseconds", required=True,
                      default=1000)
    def validate(self) -> None:
        """Extended validation.

        - `pipe_format` is required for CONNECT `pipe_mode`.
        """
        super().validate()
        if self.input_pipe_mode.value is SocketMode.CONNECT and self.input_pipe_format.value is None:
            raise Error("'input_pipe_format' required for CONNECT pipe mode.")
        if self.output_pipe_mode.value is SocketMode.CONNECT and self.output_pipe_format.value is None:
            raise Error("'output_pipe_format' required for CONNECT pipe mode.")

class DataFilterMicro(MicroService):
    """Base data provider microservice.

    Descendant classes should override:

    - `handle_input_accept_client` to validate client request and aquire resources
      associated with input pipe.
    - `handle_output_accept_client` to validate client request and aquire resources
      associated with output pipe.
    - `handle_output_produce_data` to produce data for outgoing DATA message.
    - `handle_input_accept_data` to process received data. CONSUMER only.
    - `handle_input_pipe_closed` to release resource assiciated with input pipe.
    - `handle_output_pipe_closed` to release resource assiciated with output pipe.
    """
    def initialize(self, config: DataFilterConfig) -> None:
        """Verify configuration and assemble component structural parts.
        """
        super().initialize(config)
        # Closing flag
        self.closing: bool = False
        # Configuration
        self.propagate_input_error = config.propagate_input_error.value
        # INPUT pipe
        self.input_pipe: str = config.input_pipe.value
        self.input_pipe_mode: SocketMode = config.input_pipe_mode.value
        self.input_pipe_address: ZMQAddress = config.input_pipe_address.value
        self.input_pipe_format: MIME = config.input_pipe_format.value
        self.input_batch_size: int = config.input_batch_size.value
        self.input_ready_schedule_interval: int = config.input_ready_schedule_interval.value
        #
        if self.input_pipe_mode == SocketMode.BIND:
            self.input_protocol = FBDPServer()
            self.input_protocol.on_exception = self.handle_exception
            self.input_protocol.on_accept_client = self.handle_input_accept_client
            self.input_protocol.on_schedule_ready = self.handle_input_schedule_ready
            # We have an endpoint to bind
            self.endpoints[INPUT_PIPE_CHN] = [self.input_pipe_address]
        else:
            self.input_protocol = FBDPClient()
        self.input_protocol.batch_size = self.input_batch_size
        self.input_protocol.on_pipe_closed = self.handle_input_pipe_closed
        self.input_protocol.on_accept_data = self.handle_input_accept_data
        self.input_protocol.on_get_data = self.handle_input_get_data
        # Create INPUT pipe channel
        self.pipe_in_chn: Channel = self.mngr.create_channel(DealerChannel, INPUT_PIPE_CHN,
                                                             self.input_protocol,
                                                             wait_for=Direction.IN)
        self.pipe_in_chn.protocol.log_context = self.logging_id
        # OUTPUT pipe
        self.output_pipe: str = config.output_pipe.value
        self.output_pipe_mode: SocketMode = config.output_pipe_mode.value
        self.output_pipe_address: ZMQAddress = config.output_pipe_address.value
        self.output_pipe_format: MIME = config.output_pipe_format.value
        self.output_batch_size: int = config.output_batch_size.value
        self.output_ready_schedule_interval: int = config.output_ready_schedule_interval.value
        #
        if self.output_pipe_mode == SocketMode.BIND:
            self.output_protocol = FBDPServer()
            self.output_protocol.on_exception = self.handle_exception
            self.output_protocol.on_accept_client = self.handle_output_accept_client
            self.output_protocol.on_schedule_ready = self.handle_output_schedule_ready
            # We have an endpoint to bind
            self.endpoints[OUTPUT_PIPE_CHN] = [self.output_pipe_address]
        else:
            self.output_protocol = FBDPClient()
        self.output_protocol.batch_size = self.output_batch_size
        self.output_protocol.on_pipe_closed = self.handle_output_pipe_closed
        self.output_protocol.on_produce_data = self.handle_output_produce_data
        self.output_protocol.on_get_data = self.handle_output_get_data
        # Create OUTPUT pipe channel
        self.pipe_out_chn: Channel = self.mngr.create_channel(DealerChannel, OUTPUT_PIPE_CHN,
                                                              self.output_protocol,
                                                              wait_for=Direction.IN)
        self.pipe_out_chn.protocol.log_context = self.logging_id
        # Awake channels
        self.wake_address: ZMQAddress = ZMQAddress(f'inproc://{self.peer.uid.hex}-wake')
        wake_protocol = Protocol()
        wake_protocol.handlers[ANY] = self.handle_wake_msg
        # PUSH wake
        self.wake_out_chn: Channel = self.mngr.create_channel(PushChannel, WAKE_PUSH_CHN,
                                                              wake_protocol)
        self.wake_out_chn.protocol.log_context = self.logging_id
        # PULL wake
        self.wake_in_chn: Channel = self.mngr.create_channel(PullChannel, WAKE_PULL_CHN,
                                                             wake_protocol,
                                                             wait_for=Direction.IN)
        self.wake_in_chn.protocol.log_context = self.logging_id
        # We have an endpoint to bind
        self.endpoints[WAKE_PULL_CHN] = [self.wake_address]
        #: Data to be sent to output.
        self.output: deque = deque()
    def aquire_resources(self) -> None:
        """Aquire resources required by component (open files, connect to other services etc.).

        Must raise an exception when resource aquisition fails.
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
        """Release resources aquired by component (close files, disconnect from other services etc.)
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
        """
        self.output.append(data)
        msg = SimpleMessage()
        msg.data.append(b'wake')
        self.wake_out_chn.send(msg, self.wake_out_chn.session)
    def store_batch_output(self, batch: List) -> None:
        """Store batch of data to output queue and send wake notification.
        """
        for data in batch:
            self.output.append(data)
        if self.output:
            msg = SimpleMessage()
            msg.data.append(b'wake')
            self.wake_out_chn.send(msg, self.wake_out_chn.session)
    def finish_input_processing(self, channel: Channel, session: FBDPSession, code: ErrorCode) -> None:
        """Called when input pipe is closed while output pipe will remain open.

        When code is ErrorCode.OK, the input was closed normally. Otherwise it indicates
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

        Sets service outcome to ERROR and notes exception as details.
        """
        if isinstance(exc, StopError):
            if getattr(exc, 'code', None) is ErrorCode.OK:
                return
        self.outcome = Outcome.ERROR
        self.details = exc
    def handle_input_get_data(self, channel: Channel, session: FBDPSession) -> bool:
        """Event handler executed to query the service whether is ready to accept input data.

        Returns True if output pipe is open, otherwise false.
        """
        return bool(self.pipe_in_chn.sessions)
    def handle_output_get_data(self, channel: Channel, session: FBDPSession) -> bool:
        """Event handler executed to query the data source for data availability.

        Returns True if output deque contains any data.

        Cancels the transmission by raising the `StopError` if there are no output data
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

        The session attributes `data_pipe`, `pipe_socket`, `data_format` and `params`
        contain information sent by client, and the event handler validates the request.

        If request should be rejected, it raises the `StopError` exception with `code`
        attribute containing the `ErrorCode` to be returned in CLOSE message.

        Important:
            Base implementation validates pipe identification and pipe socket, and converts
            data format from string to MIME (in session).

            The descendant class that overrides this method must call super() as first
            action.
        """
        if session.pipe != self.output_pipe:
            raise StopError(f"Unknown data pipe '{session.data_pipe}'",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # Clients can attach only to INPUT
        elif session.socket is not PipeSocket.INPUT:
            raise StopError(f"'{session.socket}' socket not available",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We work with MIME formats, so we'll convert the format specification to MIME
        session.data_format = MIME(session.data_format)
    def handle_output_accept_client(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed when client connects to OUTPUT data pipe via OPEN message.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The session attributes `data_pipe`, `pipe_socket`, `data_format` and `params`
        contain information sent by client, and the event handler validates the request.

        If request should be rejected, it raises the `StopError` exception with `code`
        attribute containing the `ErrorCode` to be returned in CLOSE message.

        Important:
            Base implementation validates pipe identification and pipe socket, and converts
            data format from string to MIME (in session).

            The descendant class that overrides this method must call super() as first
            action.
        """
        if session.pipe != self.output_pipe:
            raise StopError(f"Unknown data pipe '{session.data_pipe}'",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # Clients can attach only to our OUTPUT
        elif session.socket is not PipeSocket.OUTPUT:
            raise StopError(f"'{session.socket}' socket not available",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We work with MIME formats, so we'll convert the format specification to MIME
        session.data_format = MIME(session.data_format)
    def handle_input_schedule_ready(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed in order to send the READY message to the client later.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.

        Important:
            The base implementation schedules `resend_ready()` according to
            `ready_schedule_interval` configuration option.
        """
        self.schedule(partial(cast(FBDPServer, channel.protocol).resend_ready,
                              channel, session),
                      self.input_ready_schedule_interval)
    def handle_output_schedule_ready(self, channel: Channel, session: FBDPSession) -> None:
        """Event handler executed in order to send the READY message to the client later.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.

        Important:
            The base implementation schedules `resend_ready()` according to
            `ready_schedule_interval` configuration option.
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
            The base implementation simply raises StopError with ErrorCode.OK code, so
            the descendant class must override this method without super() call.

            The event handler must `popleft()` data from `output` queue and store them in
            `msg.data_frame` attribute. It may also set ACK-REQUEST flag and `type_data`
            attribute.

            The event handler may cancel the transmission by raising the `StopError`
            exception with `code` attribute containing the `ErrorCode` to be returned in
            CLOSE message.

        Note:
            To indicate end of data, raise StopError with ErrorCode.OK code.
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
            `store_output()` method.

            The base implementation simply raises StopError with ErrorCode.OK code, so
            the descendant class must override this method without super() call.

            The event handler may cancel the transmission by raising the `StopError`
            exception with `code` attribute containing the `ErrorCode` to be returned in
            CLOSE message.

        Note:
            The ACK-REQUEST in received DATA message is handled automatically by protocol.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_input_pipe_closed(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                                 exc: Exception=None) -> None:
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
            - Closes the output pipe it's still open  and `closing` flag is False, and if
              the input is not closed normally and `propagate_input_error` is True.
            - Sets the signal to stop the service.

            The descendant class that overrides this method must call super().
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
                for session in self.pipe_out_chn.sessions:
                    cast(FBDPServer, self.pipe_out_chn.protocol).send_close(self.pipe_out_chn,
                                                                            session, code, exc)
            # Request service to stop
            self.stop.set()
        self.closing = False
    def handle_output_pipe_closed(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                                  exc: Exception=None) -> None:
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
            - Closes the input pipe if it's still open and `closing` flag is False.
            - Sets the signal to stop the service.

            The descendant class that overrides this method must call super().
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
            for session in self.pipe_in_chn.sessions:
                cast(FBDPServer, self.pipe_in_chn.protocol).send_close(self.pipe_in_chn,
                                                                       session, code, exc)
        # Request service to stop
        self.stop.set()
        self.closing = False
