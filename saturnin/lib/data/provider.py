#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/data/provider.py
# DESCRIPTION:    Base class for Saturnin data provider microservices
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

"""Saturnin base class for data provider microservices
"""

from __future__ import annotations
from typing import cast
from functools import partial
from firebird.base.config import MIME, StrOption, EnumOption, \
     IntOption, BoolOption, ZMQAddressOption, MIMEOption
from saturnin.base import Error, StopError, Direction, SocketMode, PipeSocket, Outcome, \
     ZMQAddress, MIME, ComponentConfig, Channel, DealerChannel
from saturnin.component.micro import MicroService
from saturnin.protocol.fbdp import ErrorCode, FBDPServer, FBDPClient, \
     FBDPSession, FBDPMessage

PIPE_CHN = 'pipe'

class DataProviderConfig(ComponentConfig):
    """Base data provider microservice configuration."""
    def __init__(self, name: str):
        super().__init__(name)
        self.stop_on_close: BoolOption = \
            BoolOption('stop_on_close', "Stop service when pipe is closed", default=True)
        self.pipe: StrOption = \
            StrOption('pipe', "Data Pipe Identification", required=True)
        self.pipe_address: ZMQAddressOption = \
            ZMQAddressOption('pipe_address', "Data Pipe endpoint address", required=True)
        self.pipe_mode: EnumOption = \
            EnumOption('pipe_mode', SocketMode, "Data Pipe Mode", required=True)
        self.pipe_format: MIMEOption = \
            MIMEOption('pipe_format', "Pipe data format specification")
        self.batch_size: IntOption = \
            IntOption('batch_size', "Data batch size", required=True, default=50)
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

class DataProviderMicro(MicroService):
    """Base data provider microservice.

    Descendant classes should override:

    - `handle_accept_client` to validate client request and aquire resources associated
      with pipe.
    - `handle_produce_data` to produce data for outgoing DATA message.
    - `handle_pipe_closed` to release resource assiciated with pipe.
    """
    def initialize(self, config: DataProviderConfig) -> None:
        """Verify configuration and assemble component structural parts.
        """
        super().initialize(config)
        # PipeSocket.OUTPUT
        # Configuration
        self.stop_on_close = config.stop_on_close.value
        self.pipe: str = config.pipe.value
        self.pipe_mode: SocketMode = config.pipe_mode.value
        self.pipe_address: ZMQAddress = config.pipe_address.value
        self.pipe_format: MIME = config.pipe_format.value
        self.batch_size: int = config.batch_size.value
        self.ready_schedule_interval: int = config.ready_schedule_interval.value
        #
        if self.pipe_mode == SocketMode.BIND:
            self.protocol = FBDPServer()
            self.protocol.on_exception = self.handle_exception
            self.protocol.on_accept_client = self.handle_accept_client
            self.protocol.on_schedule_ready = self.handle_schedule_ready
            # We have an endpoint to bind
            self.endpoints[PIPE_CHN] = [self.pipe_address]
        else:
            self.protocol = FBDPClient()
        self.protocol.batch_size = self.batch_size
        self.protocol.on_pipe_closed = self.handle_pipe_closed
        self.protocol.on_produce_data = self.handle_produce_data
        # High water mark optimization
        rcvhwm = 5
        sndhwm = self.batch_size + 5
        # Create pipe channel
        chn: Channel = self.mngr.create_channel(DealerChannel, PIPE_CHN, self.protocol,
                                                wait_for=Direction.IN,
                                                sock_opts={'rcvhwm': rcvhwm,
                                                           'sndhwm': sndhwm,})
        chn.protocol.log_context = self.logging_id
    def aquire_resources(self) -> None:
        """Aquire resources required by component (open files, connect to other services etc.).

        Must raise an exception when resource aquisition fails.
        """
        # Connect to the data pipe
        if self.pipe_mode == SocketMode.CONNECT:
            chn: Channel = self.mngr.channels[PIPE_CHN]
            session = chn.connect(self.pipe_address)
            # OPEN the data pipe connection, this also fills session attributes
            # We are PRODUCER client, we must attach to server INPUT
            cast(FBDPClient, chn.protocol).send_open(chn, session, self.pipe,
                                                     PipeSocket.INPUT, self.pipe_format)
    def release_resources(self) -> None:
        """Release resources aquired by component (close files, disconnect from other services etc.)
        """
        # CLOSE all active data pipe sessions
        chn: Channel = self.mngr.channels[PIPE_CHN]
        # send_close() will discard session, so we can't iterate over sessions.values() directly
        for session in list(chn.sessions.values()):
            # We have to report error here, because normal is to close pipes before
            # shutdown is commenced. Mind that service shutdown could be also caused by error!
            cast(FBDPServer, chn.protocol).send_close(chn, session, ErrorCode.ERROR)
    def handle_exception(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                         exc: Exception) -> None:
        """Event handler called by `.handle_msg()` on exception in message handler.

        Sets service outcome to ERROR and notes exception as details.
        """
        self.outcome = Outcome.ERROR
        self.details = exc
    # FBDP server only
    def handle_accept_client(self, session: FBDPSession) -> None:
        """Event handler executed when client connects to the data pipe via OPEN message.

        Arguments:
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
        if session.pipe != self.pipe:
            raise StopError(f"Unknown data pipe '{session.data_pipe}'",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We're PRODUCER server, so clients can only attach to our OUTPUT
        elif session.socket is not PipeSocket.OUTPUT:
            raise StopError(f"'{session.socket}' socket not available",
                            code = ErrorCode.PIPE_ENDPOINT_UNAVAILABLE)
        # We work with MIME formats, so we'll convert the format specification to MIME
        session.data_format = MIME(session.data_format)
    def handle_schedule_ready(self, channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        """Event handler executed in order to send the READY message to the client later.

        Arguments:
            channel: Channel associated with data pipe.
            session: Session associated with client.
            msg:     Message that triggered the scheduling.

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.

        Important:
            The base implementation schedules `resend_ready()` according to
            `ready_schedule_interval` configuration option.
        """
        self.schedule(partial(cast(FBDPServer, channel.protocol).resend_ready,
                              channel, session, msg),
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

        The event handler may cancel the transmission by raising the `StopError` exception
        with `code` attribute containing the `ErrorCode` to be returned in CLOSE message.

        Note:
            To indicate end of data, raise StopError with ErrorCode.OK code.

        Note:
            Exceptions are handled by protocol, but only StopError is checked for protocol
            ErrorCode. As we want to report INVALID_DATA properly, we have to convert
            UnicodeError into StopError.

        Important:
            The base implementation simply raises StopError with ErrorCode.OK code, so
            the descendant class must override this method without super() call.
        """
        raise StopError('OK', code=ErrorCode.OK)
    def handle_pipe_closed(self, channel: Channel, session: FBDPSession, msg: FBDPMessage,
                           exc: Exception=None) -> None:
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
            - Stops the service if `stop_on_close` is True.

            The descendant class that overrides this method must call super().
        """
        # FDBP converts exceptions raised in our event handler to CLOSE messages, so
        # here is the central place to handle errors in data pip processing.
        # Note problem in service execution outcome
        if exc is not None:
            self.outcome = Outcome.ERROR
            self.details = exc
        #
        if self.stop_on_close:
            self.stop.set()

