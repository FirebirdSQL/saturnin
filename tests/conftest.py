#from __future__ import annotations

import pytest
from unittest.mock import MagicMock, create_autospec
import uuid

from saturnin.protocol.fbdp import (
    FBDPMessage, FBDPSession, _FBDP, FBDPServer, FBDPClient,
    MsgType, MsgFlag, ErrorCode, PipeSocket, PROTO_OPEN, PROTO_ERROR,
    FOURCC, HEADER_FMT_FULL, VERSION_MASK
)
# Ensure all necessary types for signatures are imported
from saturnin.base import Channel, InvalidMessageError, StopError, TZMQMessage, ZMQAddress, Session, Message
from firebird.base.protobuf import create_message
from firebird.butler.fbdp_pb2 import FBDPOpenDataframe
from firebird.butler.fbsd_pb2 import ErrorDescription


@pytest.fixture
def fbdp_message():
    return FBDPMessage()

@pytest.fixture
def fbdp_session():
    return FBDPSession()

@pytest.fixture
def mock_channel():
    mock = create_autospec(Channel, instance=True)
    mock.on_output_ready = MagicMock() # This is a regular method in Channel, not eventsocket
    # For eventsockets on protocol, they are handled within protocol fixtures
    mock.protocol = _FBDP() # A basic protocol for message creation by default
    mock.sessions = {}
    mock.send = MagicMock(return_value=0) # Assume send is successful by default
    mock.set_wait_out = MagicMock()
    return mock

@pytest.fixture
def fbdp_base_protocol():
    protocol = _FBDP()

    # Mock for Protocol.on_exception (which is an eventsocket)
    protocol._mock_on_exception_impl = MagicMock()
    def _mock_on_exception(channel: Channel, session: Session, msg: Message, exc: Exception) -> None:
        protocol._mock_on_exception_impl(channel, session, msg, exc)
    protocol.on_exception = _mock_on_exception

    yield protocol


@pytest.fixture
def fbdp_server_protocol():
    server = FBDPServer()

    # --- Mock FBDPServer specific event handlers ---
    server._mock_on_accept_client_impl = MagicMock() # Default: no side effect (original raises StopError)
    def _mock_on_accept_client(channel: Channel, session: FBDPSession) -> None:
        server._mock_on_accept_client_impl(channel, session)
    server.on_accept_client = _mock_on_accept_client

    server._mock_on_get_ready_impl = MagicMock(return_value=-1) # Default to use protocol.batch_size
    def _mock_on_get_ready(channel: Channel, session: FBDPSession) -> int:
        return server._mock_on_get_ready_impl(channel, session)
    server.on_get_ready = _mock_on_get_ready

    server._mock_on_schedule_ready_impl = MagicMock() # Default: no side effect (original raises StopError)
    def _mock_on_schedule_ready(channel: Channel, session: FBDPSession) -> None:
        server._mock_on_schedule_ready_impl(channel, session)
    server.on_schedule_ready = _mock_on_schedule_ready

    # --- Mock _FBDP base event handlers ---
    server._mock_on_produce_data_impl = MagicMock(side_effect=StopError("OK", code=ErrorCode.OK))
    def _mock_on_produce_data(channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        server._mock_on_produce_data_impl(channel, session, msg)
    server.on_produce_data = _mock_on_produce_data

    server._mock_on_accept_data_impl = MagicMock() # Default: no side effect (original raises StopError)
    def _mock_on_accept_data(channel: Channel, session: FBDPSession, data: bytes) -> None:
        server._mock_on_accept_data_impl(channel, session, data)
    server.on_accept_data = _mock_on_accept_data

    server._mock_on_pipe_closed_impl = MagicMock()
    def _mock_on_pipe_closed(channel: Channel, session: FBDPSession, msg: FBDPMessage, exc: Exception | None = None) -> None:
        server._mock_on_pipe_closed_impl(channel, session, msg, exc)
    server.on_pipe_closed = _mock_on_pipe_closed

    server._mock_on_noop_impl = MagicMock()
    def _mock_on_noop(channel: Channel, session: FBDPSession) -> None:
        server._mock_on_noop_impl(channel, session)
    server.on_noop = _mock_on_noop

    server._mock_on_data_confirmed_impl = MagicMock()
    def _mock_on_data_confirmed(channel: Channel, session: FBDPSession, type_data: int) -> None:
        server._mock_on_data_confirmed_impl(channel, session, type_data)
    server.on_data_confirmed = _mock_on_data_confirmed

    server._mock_on_get_data_impl = MagicMock(return_value=True) # Assume data always available/acceptable
    def _mock_on_get_data(channel: Channel, session: FBDPSession) -> bool:
        return server._mock_on_get_data_impl(channel, session)
    server.on_get_data = _mock_on_get_data

    # Mock for Protocol.on_exception (inherited by FBDPServer)
    server._mock_on_exception_impl = MagicMock()
    def _mock_on_exception(channel: Channel, session: Session, msg: Message, exc: Exception) -> None:
        server._mock_on_exception_impl(channel, session, msg, exc)
    server.on_exception = _mock_on_exception

    yield server

@pytest.fixture
def fbdp_client_protocol():
    client = FBDPClient()

    # --- Mock FBDPClient specific event handlers ---
    client._mock_on_server_ready_impl = MagicMock(return_value=-1) # Default to use protocol.batch_size
    def _mock_on_server_ready(channel: Channel, session: FBDPSession, batch_size: int) -> int:
        return client._mock_on_server_ready_impl(channel, session, batch_size)
    client.on_server_ready = _mock_on_server_ready

    client._mock_on_init_session_impl = MagicMock()
    def _mock_on_init_session(channel: Channel, session: FBDPSession) -> None:
        client._mock_on_init_session_impl(channel, session)
    client.on_init_session = _mock_on_init_session

    # --- Mock _FBDP base event handlers (as for server) ---
    client._mock_on_produce_data_impl = MagicMock(side_effect=StopError("OK", code=ErrorCode.OK))
    def _mock_on_produce_data(channel: Channel, session: FBDPSession, msg: FBDPMessage) -> None:
        client._mock_on_produce_data_impl(channel, session, msg)
    client.on_produce_data = _mock_on_produce_data

    client._mock_on_accept_data_impl = MagicMock()
    def _mock_on_accept_data(channel: Channel, session: FBDPSession, data: bytes) -> None:
        client._mock_on_accept_data_impl(channel, session, data)
    client.on_accept_data = _mock_on_accept_data

    client._mock_on_pipe_closed_impl = MagicMock()
    def _mock_on_pipe_closed(channel: Channel, session: FBDPSession, msg: FBDPMessage, exc: Exception | None = None) -> None:
        client._mock_on_pipe_closed_impl(channel, session, msg, exc)
    client.on_pipe_closed = _mock_on_pipe_closed

    client._mock_on_noop_impl = MagicMock()
    def _mock_on_noop(channel: Channel, session: FBDPSession) -> None:
        client._mock_on_noop_impl(channel, session)
    client.on_noop = _mock_on_noop

    client._mock_on_data_confirmed_impl = MagicMock()
    def _mock_on_data_confirmed(channel: Channel, session: FBDPSession, type_data: int) -> None:
        client._mock_on_data_confirmed_impl(channel, session, type_data)
    client.on_data_confirmed = _mock_on_data_confirmed

    client._mock_on_get_data_impl = MagicMock(return_value=True)
    def _mock_on_get_data(channel: Channel, session: FBDPSession) -> bool:
        return client._mock_on_get_data_impl(channel, session)
    client.on_get_data = _mock_on_get_data

    # Mock for Protocol.on_exception (inherited by FBDPClient)
    client._mock_on_exception_impl = MagicMock()
    def _mock_on_exception(channel: Channel, session: Session, msg: Message, exc: Exception) -> None:
        client._mock_on_exception_impl(channel, session, msg, exc)
    client.on_exception = _mock_on_exception

    yield client

# Helper to create a valid ZMQ header
def create_fbdp_header_bytes(msg_type: MsgType, flags: MsgFlag = MsgFlag.NONE, type_data: int = 0, version: int = _FBDP.REVISION) -> bytes:
    from struct import pack
    control_byte = (msg_type.value << 3) | version
    return pack(HEADER_FMT_FULL, FOURCC, control_byte, flags.value, type_data)
