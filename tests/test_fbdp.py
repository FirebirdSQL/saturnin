import pytest
from unittest.mock import MagicMock, patch, ANY as MockANY
import uuid
from struct import pack, unpack

from saturnin.protocol.fbdp import (
    FBDPMessage, FBDPSession, _FBDP, FBDPServer, FBDPClient,
    MsgType, MsgFlag, ErrorCode, PipeSocket, PROTO_OPEN, PROTO_ERROR,
    FOURCC, HEADER_FMT_FULL, HEADER_FMT, VERSION_MASK, DATA_BATCH_SIZE
)
# Ensure all necessary types for signatures are imported
from saturnin.base import Channel, InvalidMessageError, StopError, TZMQMessage, ZMQAddress, Session, Message
from firebird.base.protobuf import create_message, struct2dict
from firebird.butler.fbdp_pb2 import FBDPOpenDataframe
from firebird.butler.fbsd_pb2 import ErrorDescription

# Import helper from conftest
from conftest import create_fbdp_header_bytes

class TestFBDPMessage:
    def test_fbdp_message_init(self, fbdp_message):
        assert fbdp_message.msg_type == MsgType.UNKNOWN
        assert fbdp_message.flags == MsgFlag(0)
        assert fbdp_message.type_data == 0
        assert fbdp_message.data_frame is None

    def test_fbdp_message_str_repr(self, fbdp_message):
        fbdp_message.msg_type = MsgType.OPEN
        assert str(fbdp_message) == "FBDPMessage[OPEN]"
        assert repr(fbdp_message) == "FBDPMessage[OPEN]"

    def test_from_zmsg_open(self, fbdp_message):
        open_df = create_message(PROTO_OPEN)
        open_df.data_pipe = "test_pipe"
        open_df.pipe_socket = PipeSocket.INPUT.value
        open_df.data_format = "text/plain"
        open_df.parameters.update({"key": "value"})

        zmsg = [
            create_fbdp_header_bytes(MsgType.OPEN, type_data=123),
            open_df.SerializeToString()
        ]
        fbdp_message.from_zmsg(zmsg)

        assert fbdp_message.msg_type == MsgType.OPEN
        assert fbdp_message.flags == MsgFlag.NONE
        assert fbdp_message.type_data == 123
        assert isinstance(fbdp_message.data_frame, FBDPOpenDataframe)
        assert fbdp_message.data_frame.data_pipe == "test_pipe"
        assert fbdp_message.data_frame.pipe_socket == PipeSocket.INPUT.value
        assert fbdp_message.data_frame.data_format == "text/plain"
        assert struct2dict(fbdp_message.data_frame.parameters) == {"key": "value"}

    def test_as_zmsg_open(self, fbdp_message):
        fbdp_message.msg_type = MsgType.OPEN
        fbdp_message.flags = MsgFlag.ACK_REQ
        fbdp_message.type_data = 456
        fbdp_message.data_frame = create_message(PROTO_OPEN)
        fbdp_message.data_frame.data_pipe = "another_pipe"
        fbdp_message.data_frame.pipe_socket = PipeSocket.OUTPUT.value
        fbdp_message.data_frame.data_format = "application/octet-stream"

        zmsg = fbdp_message.as_zmsg()
        assert len(zmsg) == 2
        control_byte, flags, type_data = unpack(HEADER_FMT, zmsg[0])
        assert MsgType(control_byte >> 3) == MsgType.OPEN
        assert MsgFlag(flags) == MsgFlag.ACK_REQ
        assert type_data == 456

        parsed_df = create_message(PROTO_OPEN)
        parsed_df.ParseFromString(zmsg[1])
        assert parsed_df.data_pipe == "another_pipe"

    def test_from_zmsg_data(self, fbdp_message):
        zmsg = [
            create_fbdp_header_bytes(MsgType.DATA, type_data=789),
            b"some_payload"
        ]
        fbdp_message.from_zmsg(zmsg)
        assert fbdp_message.msg_type == MsgType.DATA
        assert fbdp_message.type_data == 789
        assert fbdp_message.data_frame == b"some_payload"

    def test_as_zmsg_data(self, fbdp_message):
        fbdp_message.msg_type = MsgType.DATA
        fbdp_message.data_frame = b"payload_data"
        zmsg = fbdp_message.as_zmsg()
        assert len(zmsg) == 2
        assert zmsg[1] == b"payload_data"

    def test_from_zmsg_close_with_errors(self, fbdp_message):
        err1 = create_message(PROTO_ERROR)
        err1.code = 10
        err1.description = "Error 1"
        err2 = create_message(PROTO_ERROR)
        err2.code = 20
        err2.description = "Error 2"

        zmsg = [
            create_fbdp_header_bytes(MsgType.CLOSE, type_data=ErrorCode.ERROR.value),
            err1.SerializeToString(),
            err2.SerializeToString()
        ]
        fbdp_message.from_zmsg(zmsg)
        assert fbdp_message.msg_type == MsgType.CLOSE
        assert fbdp_message.type_data == ErrorCode.ERROR
        assert len(fbdp_message.data_frame) == 2
        assert fbdp_message.data_frame[0].description == "Error 1"
        assert fbdp_message.data_frame[1].code == 20

    def test_as_zmsg_close_with_errors(self, fbdp_message):
        fbdp_message.msg_type = MsgType.CLOSE
        fbdp_message.type_data = ErrorCode.INTERNAL_ERROR
        fbdp_message.data_frame = []
        err1_desc = "Error A"
        err1 = create_message(PROTO_ERROR)
        err1.description = err1_desc
        fbdp_message.data_frame.append(err1)

        zmsg = fbdp_message.as_zmsg()
        assert len(zmsg) == 2
        control_byte, flags, type_data = unpack(HEADER_FMT, zmsg[0])
        assert MsgType(control_byte >> 3) == MsgType.CLOSE
        assert ErrorCode(type_data) == ErrorCode.INTERNAL_ERROR

        parsed_err = create_message(PROTO_ERROR)
        parsed_err.ParseFromString(zmsg[1])
        assert parsed_err.description == err1_desc

    def test_from_zmsg_invalid_message(self, fbdp_message):
        with pytest.raises(InvalidMessageError):
            fbdp_message.from_zmsg([b"invalid_header_too_short"]) # Header too short

        with pytest.raises(InvalidMessageError):
            # Valid header, but OPEN message expects a data frame
            fbdp_message.from_zmsg([create_fbdp_header_bytes(MsgType.OPEN)])

    def test_clear(self, fbdp_message):
        fbdp_message.msg_type = MsgType.DATA
        fbdp_message.flags = MsgFlag.ACK_REQ
        fbdp_message.type_data = 1
        fbdp_message.data_frame = b"data"
        fbdp_message.clear()
        assert fbdp_message.msg_type == MsgType.UNKNOWN
        assert fbdp_message.flags == MsgFlag(0)
        assert fbdp_message.type_data == 0
        assert fbdp_message.data_frame is None

    def test_copy_open(self, fbdp_message):
        original_open_df = create_message(PROTO_OPEN)
        original_open_df.data_pipe = "pipe_to_copy"
        original_open_df.pipe_socket = PipeSocket.INPUT.value

        fbdp_message.msg_type = MsgType.OPEN
        fbdp_message.data_frame = original_open_df
        fbdp_message.type_data = 123

        copied_msg = fbdp_message.copy()

        assert isinstance(copied_msg, FBDPMessage)
        assert copied_msg.msg_type == MsgType.OPEN
        assert copied_msg.type_data == 123
        assert copied_msg.data_frame is not original_open_df # Should be a new instance
        assert copied_msg.data_frame.data_pipe == "pipe_to_copy"
        assert copied_msg.data_frame.pipe_socket == PipeSocket.INPUT.value

    def test_copy_data(self, fbdp_message):
        fbdp_message.msg_type = MsgType.DATA
        fbdp_message.data_frame = b"some data"
        copied_msg = fbdp_message.copy()
        assert copied_msg.msg_type == MsgType.DATA
        assert copied_msg.data_frame == b"some data" # bytes are immutable, so same ref is fine

    def test_copy_close(self, fbdp_message):
        fbdp_message.msg_type = MsgType.CLOSE
        fbdp_message.type_data = ErrorCode.OK.value
        original_err = create_message(PROTO_ERROR)
        original_err.description = "Test Error for Copy"
        fbdp_message.data_frame = [original_err]

        copied_msg = fbdp_message.copy()
        assert copied_msg.msg_type == MsgType.CLOSE
        assert copied_msg.type_data == ErrorCode.OK.value
        assert len(copied_msg.data_frame) == 1
        assert copied_msg.data_frame[0] is not original_err # Should be a new instance
        assert copied_msg.data_frame[0].description == "Test Error for Copy"


    def test_get_keys(self, fbdp_message):
        fbdp_message.msg_type = MsgType.READY
        assert fbdp_message.get_keys() == [MsgType.READY, MockANY]

    def test_get_header(self, fbdp_message):
        fbdp_message.msg_type = MsgType.DATA
        fbdp_message.flags = MsgFlag.ACK_REQ
        fbdp_message.type_data = 99
        header = fbdp_message.get_header()
        fourcc, control_byte, flags, type_data = unpack(HEADER_FMT_FULL, header)
        assert fourcc == FOURCC
        assert (control_byte & VERSION_MASK) == _FBDP.REVISION
        assert MsgType(control_byte >> 3) == MsgType.DATA
        assert MsgFlag(flags) == MsgFlag.ACK_REQ
        assert type_data == 99

    def test_flag_methods(self, fbdp_message):
        assert not fbdp_message.has_ack_req()
        assert not fbdp_message.has_ack_reply()

        fbdp_message.set_flag(MsgFlag.ACK_REQ)
        assert fbdp_message.has_ack_req()
        assert not fbdp_message.has_ack_reply()
        assert fbdp_message.flags == MsgFlag.ACK_REQ

        fbdp_message.set_flag(MsgFlag.ACK_REPLY)
        assert fbdp_message.has_ack_req() # Still has ACK_REQ
        assert fbdp_message.has_ack_reply()
        assert fbdp_message.flags == (MsgFlag.ACK_REQ | MsgFlag.ACK_REPLY)

        fbdp_message.clear_flag(MsgFlag.ACK_REQ)
        assert not fbdp_message.has_ack_req()
        assert fbdp_message.has_ack_reply()
        assert fbdp_message.flags == MsgFlag.ACK_REPLY

    def test_note_exception(self, fbdp_message):
        fbdp_message.msg_type = MsgType.CLOSE # Note_exception is for CLOSE messages
        fbdp_message.data_frame = [] # Initialize as list

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            fbdp_message.note_exception(e)

        assert len(fbdp_message.data_frame) == 1
        err_desc = fbdp_message.data_frame[0]
        assert isinstance(err_desc, ErrorDescription)
        assert err_desc.description == "Test exception"
        assert err_desc.code == 0 # Default if not set

        fbdp_message.data_frame = []
        class CustomError(Exception):
            def __init__(self, message, code):
                super().__init__(message)
                self.code = code
        try:
            raise CustomError("Custom error with code", 12345)
        except CustomError as e:
            fbdp_message.note_exception(e)

        assert len(fbdp_message.data_frame) == 1
        err_desc = fbdp_message.data_frame[0]
        assert err_desc.description == "Custom error with code"
        assert err_desc.code == 12345


class TestFBDProtocolBase:
    def test_validate_empty_message(self, fbdp_base_protocol):
        with pytest.raises(InvalidMessageError, match="Empty message"):
            fbdp_base_protocol.validate([])

    def test_validate_header_too_short(self, fbdp_base_protocol):
        with pytest.raises(InvalidMessageError, match="Message header must be 8 bytes long"):
            fbdp_base_protocol.validate([b"short"])

    def test_validate_invalid_fourcc(self, fbdp_base_protocol):
        header = pack(HEADER_FMT_FULL, b'XXXX', (MsgType.NOOP.value << 3) | _FBDP.REVISION, 0, 0)
        with pytest.raises(InvalidMessageError, match="Invalid FourCC"):
            fbdp_base_protocol.validate([header])

    def test_validate_invalid_version(self, fbdp_base_protocol):
        invalid_version = (_FBDP.REVISION + 1) & VERSION_MASK # Ensure it's different
        header = pack(HEADER_FMT_FULL, FOURCC, (MsgType.NOOP.value << 3) | invalid_version, 0, 0)
        with pytest.raises(InvalidMessageError, match="Invalid protocol version"):
            fbdp_base_protocol.validate([header])

    def test_validate_invalid_flags(self, fbdp_base_protocol):
        invalid_flags = 0b100 # Bit 2 is not used by ACK_REQ or ACK_REPLY
        header = pack(HEADER_FMT_FULL, FOURCC, (MsgType.NOOP.value << 3) | _FBDP.REVISION, invalid_flags, 0)
        with pytest.raises(InvalidMessageError, match="Invalid flags"):
            fbdp_base_protocol.validate([header])

    def test_validate_illegal_message_type(self, fbdp_base_protocol):
        # MsgType 0 is UNKNOWN and invalid, or use a number > max valid MsgType
        header = pack(HEADER_FMT_FULL, FOURCC, (0 << 3) | _FBDP.REVISION, 0, 0)
        with pytest.raises(InvalidMessageError, match="Illegal message type 0"):
            fbdp_base_protocol.validate([header])

    def test_validate_open_missing_dataframe(self, fbdp_base_protocol):
        header = create_fbdp_header_bytes(MsgType.OPEN)
        with pytest.raises(InvalidMessageError, match="OPEN message must have a dataframe"):
            fbdp_base_protocol.validate([header])

    def test_validate_open_invalid_dataframe_proto(self, fbdp_base_protocol):
        header = create_fbdp_header_bytes(MsgType.OPEN)
        with pytest.raises(InvalidMessageError, match="Invalid data frame for OPEN message"):
            fbdp_base_protocol.validate([header, b"not_a_protobuf"])

    def test_validate_open_missing_fields(self, fbdp_base_protocol):
        header = create_fbdp_header_bytes(MsgType.OPEN)
        open_df = create_message(PROTO_OPEN) # Missing required fields
        with pytest.raises(InvalidMessageError, match="Invalid data frame for OPEN message"):
            fbdp_base_protocol.validate([header, open_df.SerializeToString()])

    def test_validate_close_invalid_error_description(self, fbdp_base_protocol):
        header = create_fbdp_header_bytes(MsgType.CLOSE)
        # ErrorDescription with missing 'description' field
        bad_err_df = ErrorDescription()
        bad_err_df.code = 1
        # No, this will not fail validation, as ParseFromString will not complain for missing description
        # The check is `if not fpb.description:`
        # Need to check how protobuf handles unset string fields (empty string vs. None)
        # It defaults to empty string. So an empty string for description is also invalid here.
        with pytest.raises(InvalidMessageError, match="Missing error description"):
            fbdp_base_protocol.validate([header, bad_err_df.SerializeToString()])

    def test_validate_data_too_many_frames(self, fbdp_base_protocol):
        header = create_fbdp_header_bytes(MsgType.DATA)
        with pytest.raises(InvalidMessageError, match="DATA message may have only one data frame"):
            fbdp_base_protocol.validate([header, b"data1", b"data2"])

    def test_validate_ready_noop_with_data_frames(self, fbdp_base_protocol):
        header_ready = create_fbdp_header_bytes(MsgType.READY)
        with pytest.raises(InvalidMessageError, match="Data frames not allowed for READY and NOOP messages"):
            fbdp_base_protocol.validate([header_ready, b"data"])

        header_noop = create_fbdp_header_bytes(MsgType.NOOP)
        with pytest.raises(InvalidMessageError, match="Data frames not allowed for READY and NOOP messages"):
            fbdp_base_protocol.validate([header_noop, b"data"])

    def test_validate_valid_open_message(self, fbdp_base_protocol):
        header = create_fbdp_header_bytes(MsgType.OPEN)
        open_df = create_message(PROTO_OPEN)
        open_df.data_pipe = "test_pipe"
        open_df.pipe_socket = PipeSocket.INPUT.value
        open_df.data_format = "text/plain"
        fbdp_base_protocol.validate([header, open_df.SerializeToString()]) # Should not raise

    def test_create_message_for(self, fbdp_base_protocol):
        msg = fbdp_base_protocol.create_message_for(MsgType.READY, type_data=DATA_BATCH_SIZE, flags=MsgFlag.ACK_REQ)
        assert isinstance(msg, FBDPMessage)
        assert msg.msg_type == MsgType.READY
        assert msg.type_data == DATA_BATCH_SIZE
        assert msg.flags == MsgFlag.ACK_REQ
        assert msg.data_frame is None # READY has no data_frame

        msg_open = fbdp_base_protocol.create_message_for(MsgType.OPEN)
        assert msg_open.msg_type == MsgType.OPEN
        assert isinstance(msg_open.data_frame, FBDPOpenDataframe)

        msg_close = fbdp_base_protocol.create_message_for(MsgType.CLOSE)
        assert msg_close.msg_type == MsgType.CLOSE
        assert isinstance(msg_close.data_frame, list)


    def test_create_ack_reply(self, fbdp_base_protocol):
        original_msg = FBDPMessage()
        original_msg.msg_type = MsgType.DATA
        original_msg.type_data = 123
        original_msg.flags = MsgFlag.ACK_REQ

        reply_msg = fbdp_base_protocol.create_ack_reply(original_msg)
        assert reply_msg.msg_type == MsgType.DATA
        assert reply_msg.type_data == 123
        assert reply_msg.flags == MsgFlag.ACK_REPLY # ACK_REQ cleared, ACK_REPLY set

    def test_handle_exception(self, fbdp_base_protocol, mock_channel, fbdp_session):
        # The fbdp_base_protocol fixture already sets up a mock for on_exception
        test_exception = ValueError("Test Error")
        test_msg = FBDPMessage()
        test_msg.msg_type = MsgType.DATA

        with patch.object(fbdp_base_protocol, 'send_close') as mock_send_close:
            fbdp_base_protocol.handle_exception(mock_channel, fbdp_session, test_msg, test_exception)

            mock_send_close.assert_called_once_with(mock_channel, fbdp_session, ErrorCode.INTERNAL_ERROR, test_exception)
            # Assert on the underlying implementation mock
            fbdp_base_protocol._mock_on_exception_impl.assert_called_once_with(mock_channel, fbdp_session, test_msg, test_exception)

    def test_handle_exception_with_stop_error(self, fbdp_base_protocol, mock_channel, fbdp_session):
        # The fbdp_base_protocol fixture already sets up a mock for on_exception
        stop_exception = StopError("Stop with code", code=ErrorCode.INVALID_DATA)
        test_msg = FBDPMessage()

        with patch.object(fbdp_base_protocol, 'send_close') as mock_send_close:
            fbdp_base_protocol.handle_exception(mock_channel, fbdp_session, test_msg, stop_exception)
            mock_send_close.assert_called_once_with(mock_channel, fbdp_session, ErrorCode.INVALID_DATA, stop_exception)
            fbdp_base_protocol._mock_on_exception_impl.assert_called_once_with(mock_channel, fbdp_session, test_msg, stop_exception)

    def test_handle_noop_msg(self, fbdp_server_protocol, mock_channel, fbdp_session): # Use server or client fixture
        noop_msg = FBDPMessage()
        noop_msg.msg_type = MsgType.NOOP
        # on_noop is mocked in fbdp_server_protocol fixture

        fbdp_server_protocol.handle_noop_msg(mock_channel, fbdp_session, noop_msg)
        mock_channel.send.assert_not_called()
        fbdp_server_protocol._mock_on_noop_impl.assert_called_once_with(mock_channel, fbdp_session)

    def test_handle_noop_msg_ack_req(self, fbdp_server_protocol, mock_channel, fbdp_session): # Use server or client fixture
        noop_msg = FBDPMessage()
        noop_msg.msg_type = MsgType.NOOP
        noop_msg.set_flag(MsgFlag.ACK_REQ)
        # on_noop is mocked in fbdp_server_protocol fixture

        fbdp_server_protocol.handle_noop_msg(mock_channel, fbdp_session, noop_msg)
        mock_channel.send.assert_called_once()
        sent_msg = mock_channel.send.call_args[0][0]
        assert sent_msg.msg_type == MsgType.NOOP
        assert sent_msg.has_ack_reply()
        assert not sent_msg.has_ack_req()
        fbdp_server_protocol._mock_on_noop_impl.assert_called_once_with(mock_channel, fbdp_session)

class TestFBDPServer:
    def test_server_handle_open_msg(self, fbdp_server_protocol, mock_channel, fbdp_session):
        open_msg = fbdp_server_protocol.create_message_for(MsgType.OPEN)
        open_msg.data_frame.data_pipe = "server_pipe_1"
        open_msg.data_frame.pipe_socket = PipeSocket.INPUT.value
        open_msg.data_frame.data_format = "application/json"

        with patch.object(fbdp_server_protocol, 'send_ready') as mock_send_ready:
            fbdp_server_protocol.handle_open_msg(mock_channel, fbdp_session, open_msg)

        fbdp_server_protocol._mock_on_accept_client_impl.assert_called_once_with(mock_channel, fbdp_session)
        assert fbdp_session.pipe == "server_pipe_1"
        assert fbdp_session.socket == PipeSocket.INPUT
        assert fbdp_session.data_format == "application/json"
        mock_send_ready.assert_called_once()
        assert fbdp_session.await_ready

    def test_server_handle_open_msg_protocol_violation(self, fbdp_server_protocol, mock_channel, fbdp_session):
        fbdp_session.pipe = "already_set" # Simulate already open session
        open_msg = fbdp_server_protocol.create_message_for(MsgType.OPEN)
        with pytest.raises(StopError, match="Out of band OPEN message") as exc_info:
            fbdp_server_protocol.handle_open_msg(mock_channel, fbdp_session, open_msg)
        assert exc_info.value.code == ErrorCode.PROTOCOL_VIOLATION

    def test_server_handle_ready_msg_from_client(self, fbdp_server_protocol, mock_channel, fbdp_session):
        fbdp_session.await_ready = True # Server is waiting for client's READY
        fbdp_session.socket = PipeSocket.OUTPUT # Server will produce data

        ready_msg = fbdp_server_protocol.create_message_for(MsgType.READY, type_data=10) # Client wants 10
        fbdp_server_protocol.handle_ready_msg(mock_channel, fbdp_session, ready_msg)

        assert not fbdp_session.await_ready
        assert fbdp_session.transmit == 10
        mock_channel.set_wait_out.assert_called_once_with(True, fbdp_session)

    def test_server_handle_ready_msg_client_not_ready(self, fbdp_server_protocol, mock_channel, fbdp_session):
        fbdp_session.await_ready = True
        ready_msg = fbdp_server_protocol.create_message_for(MsgType.READY, type_data=0)
        fbdp_server_protocol.handle_ready_msg(mock_channel, fbdp_session, ready_msg)
        fbdp_server_protocol._mock_on_schedule_ready_impl.assert_called_once_with(mock_channel, fbdp_session)

    def test_server_init_new_batch(self, fbdp_server_protocol, mock_channel, fbdp_session):
        fbdp_server_protocol.batch_size = 20
        # _mock_on_get_ready_impl is already set to return -1 in the fixture

        with patch.object(fbdp_server_protocol, 'send_ready') as mock_send_ready:
            fbdp_server_protocol._init_new_batch(mock_channel, fbdp_session)

        fbdp_server_protocol._mock_on_get_ready_impl.assert_called_with(mock_channel, fbdp_session)
        mock_send_ready.assert_called_once_with(mock_channel, fbdp_session, 20)
        assert fbdp_session.transmit is None
        assert fbdp_session.await_ready

    def test_server_resend_ready(self, fbdp_server_protocol, mock_channel):
        # Create a session and add it to the channel manually for this test
        session = FBDPSession()
        session.routing_id = b"client1"
        mock_channel.sessions = {session.routing_id: session}

        fbdp_server_protocol.batch_size = 15
        with patch.object(fbdp_server_protocol, 'send_ready') as mock_send_ready:
            fbdp_server_protocol.resend_ready(mock_channel, session)
        mock_send_ready.assert_called_once_with(mock_channel, session, 15)
        assert session.await_ready

    def test_server_handle_data_msg_as_consumer(self, fbdp_server_protocol, mock_channel, fbdp_session):
        fbdp_server_protocol._flow_in_socket = PipeSocket.INPUT
        fbdp_session.socket = PipeSocket.INPUT
        fbdp_session.transmit = 1
        data_msg = fbdp_server_protocol.create_message_for(MsgType.DATA)
        data_msg.data_frame = b"consumed_data"

        fbdp_server_protocol.handle_data_msg(mock_channel, fbdp_session, data_msg)

        fbdp_server_protocol._mock_on_accept_data_impl.assert_called_once_with(mock_channel, fbdp_session, b"consumed_data")
        assert fbdp_session.transmit is None
        fbdp_server_protocol._mock_on_get_ready_impl.assert_called() # Part of _init_new_batch

class TestFBDPClient:
    def test_client_send_open(self, fbdp_client_protocol, mock_channel, fbdp_session):
        pipe_name = "client_pipe_1"
        pipe_socket = PipeSocket.INPUT
        data_format = "text/xml"
        params = {"timeout": "1000"}

        fbdp_client_protocol.send_open(mock_channel, fbdp_session, pipe_name, pipe_socket, data_format, params)

        mock_channel.send.assert_called_once()
        sent_msg = mock_channel.send.call_args[0][0]
        assert sent_msg.msg_type == MsgType.OPEN
        assert sent_msg.data_frame.data_pipe == pipe_name
        assert sent_msg.data_frame.pipe_socket == pipe_socket.value
        assert sent_msg.data_frame.data_format == data_format
        assert struct2dict(sent_msg.data_frame.parameters) == params

        assert mock_channel.on_output_ready == fbdp_client_protocol._on_output_ready
        assert fbdp_session.pipe == pipe_name
        assert fbdp_session.socket == pipe_socket
        assert fbdp_session.data_format == data_format
        assert fbdp_session.params == params

        fbdp_client_protocol._mock_on_init_session_impl.assert_called_once_with(mock_channel, fbdp_session)

    def test_client_handle_ready_msg_from_server(self, fbdp_client_protocol, mock_channel, fbdp_session):
        fbdp_session.socket = PipeSocket.INPUT
        fbdp_client_protocol.batch_size = 25
        server_ready_msg = fbdp_client_protocol.create_message_for(MsgType.READY, type_data=30)
        fbdp_client_protocol._mock_on_server_ready_impl.return_value = 20

        with patch.object(fbdp_client_protocol, 'send_ready') as mock_send_ready_by_client:
            fbdp_client_protocol.handle_ready_msg(mock_channel, fbdp_session, server_ready_msg)

        fbdp_client_protocol._mock_on_server_ready_impl.assert_called_once_with(mock_channel, fbdp_session, 30)
        mock_send_ready_by_client.assert_called_once_with(mock_channel, fbdp_session, 20)
        assert fbdp_session.transmit == 20
        mock_channel.set_wait_out.assert_called_once_with(True, fbdp_session)

    def test_client_handle_ready_msg_server_not_ready(self, fbdp_client_protocol, mock_channel, fbdp_session):
        server_ready_msg = fbdp_client_protocol.create_message_for(MsgType.READY, type_data=0) # Server sends 0

        with patch.object(fbdp_client_protocol, 'send_ready') as mock_send_ready_by_client:
            fbdp_client_protocol.handle_ready_msg(mock_channel, fbdp_session, server_ready_msg)

        mock_send_ready_by_client.assert_called_once_with(mock_channel, fbdp_session, 0) # Client confirms 0
        assert fbdp_session.transmit is None # Transmission not started

    def test_client_handle_unexpected_open_msg(self, fbdp_client_protocol, mock_channel, fbdp_session):
        open_msg_from_server = fbdp_client_protocol.create_message_for(MsgType.OPEN)
        with pytest.raises(StopError, match="OPEN message received from server") as exc_info:
            fbdp_client_protocol.handle_open_msg(mock_channel, fbdp_session, open_msg_from_server)
        assert exc_info.value.code == ErrorCode.PROTOCOL_VIOLATION

    def test_client_handle_data_msg_as_producer_ack_reply(self, fbdp_client_protocol, mock_channel, fbdp_session):
        fbdp_client_protocol._flow_in_socket = PipeSocket.INPUT
        fbdp_session.socket = PipeSocket.OUTPUT
        fbdp_session.transmit = 5
        fbdp_client_protocol.send_after_confirmed = True

        ack_reply_msg = fbdp_client_protocol.create_message_for(MsgType.DATA, type_data=1)
        ack_reply_msg.set_flag(MsgFlag.ACK_REPLY)

        fbdp_client_protocol.handle_data_msg(mock_channel, fbdp_session, ack_reply_msg)

        fbdp_client_protocol._mock_on_data_confirmed_impl.assert_called_once_with(mock_channel, fbdp_session, 1)
        mock_channel.set_wait_out.assert_called_once_with(True, fbdp_session)

    def test_accept_new_session_is_false(self, fbdp_client_protocol, mock_channel):
        assert not fbdp_client_protocol.accept_new_session(mock_channel, b"some_id", FBDPMessage())

    def test_connect_with_session_is_true(self, fbdp_client_protocol, mock_channel):
        assert fbdp_client_protocol.connect_with_session(mock_channel)

# More complex flow simulation might be needed for _send_data and its interactions
# with on_get_data, on_produce_data, and channel.set_wait_out.
# These would be more like integration tests within the unit test file.
# Example structure:
#
# @patch('saturnin.protocol.fbdp._FBDP.on_produce_data', new_callable=MagicMock)
# def test_server_send_data_flow(self, mock_on_produce_data, fbdp_server_protocol, mock_channel, fbdp_session):
#     # Setup session for sending data
#     fbdp_session.transmit = 1
#     fbdp_session.socket = PipeSocket.OUTPUT # Server is producer
#     fbdp_server_protocol._flow_in_socket = PipeSocket.INPUT # Data flows to INPUT from server's POV
#
#     # Mock on_produce_data to populate the message
#     def populate_data_frame(channel, session, msg):
#         msg.data_frame = b"produced_by_server"
#     mock_on_produce_data.side_effect = populate_data_frame
#     fbdp_server_protocol.on_produce_data = mock_on_produce_data
#
#     # Create a data message to be populated
#     data_msg_to_send = fbdp_server_protocol.create_message_for(MsgType.DATA)
#
#     fbdp_server_protocol._send_data(mock_channel, fbdp_session, data_msg_to_send)
#
#     mock_on_produce_data.assert_called_once_with(mock_channel, fbdp_session, data_msg_to_send)
#     mock_channel.send.assert_called_once()
#     sent_msg = mock_channel.send.call_args[0][0]
#     assert sent_msg.data_frame == b"produced_by_server"
#     assert fbdp_session.transmit == 0
#     # _init_new_batch should be called
#     fbdp_server_protocol.on_get_ready.assert_called_once()
