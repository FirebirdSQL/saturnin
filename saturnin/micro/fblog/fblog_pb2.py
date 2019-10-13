# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: saturnin/micro/fblog/fblog.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
from google.protobuf import struct_pb2 as google_dot_protobuf_dot_struct__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='saturnin/micro/fblog/fblog.proto',
  package='saturnin.protobuf',
  syntax='proto3',
  serialized_pb=_b('\n saturnin/micro/fblog/fblog.proto\x12\x11saturnin.protobuf\x1a\x1fgoogle/protobuf/timestamp.proto\x1a\x1cgoogle/protobuf/struct.proto\"\xa8\x01\n\x10\x46irebirdLogEntry\x12\x0e\n\x06origin\x18\x01 \x01(\t\x12-\n\ttimestamp\x18\x02 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\r\n\x05level\x18\x03 \x01(\r\x12\x0c\n\x04\x63ode\x18\x04 \x01(\r\x12\x0f\n\x07message\x18\x05 \x01(\t\x12\'\n\x06params\x18\x06 \x01(\x0b\x32\x17.google.protobuf.Structb\x06proto3')
  ,
  dependencies=[google_dot_protobuf_dot_timestamp__pb2.DESCRIPTOR,google_dot_protobuf_dot_struct__pb2.DESCRIPTOR,])




_FIREBIRDLOGENTRY = _descriptor.Descriptor(
  name='FirebirdLogEntry',
  full_name='saturnin.protobuf.FirebirdLogEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='origin', full_name='saturnin.protobuf.FirebirdLogEntry.origin', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timestamp', full_name='saturnin.protobuf.FirebirdLogEntry.timestamp', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='level', full_name='saturnin.protobuf.FirebirdLogEntry.level', index=2,
      number=3, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='code', full_name='saturnin.protobuf.FirebirdLogEntry.code', index=3,
      number=4, type=13, cpp_type=3, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='message', full_name='saturnin.protobuf.FirebirdLogEntry.message', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='params', full_name='saturnin.protobuf.FirebirdLogEntry.params', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=119,
  serialized_end=287,
)

_FIREBIRDLOGENTRY.fields_by_name['timestamp'].message_type = google_dot_protobuf_dot_timestamp__pb2._TIMESTAMP
_FIREBIRDLOGENTRY.fields_by_name['params'].message_type = google_dot_protobuf_dot_struct__pb2._STRUCT
DESCRIPTOR.message_types_by_name['FirebirdLogEntry'] = _FIREBIRDLOGENTRY
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

FirebirdLogEntry = _reflection.GeneratedProtocolMessageType('FirebirdLogEntry', (_message.Message,), dict(
  DESCRIPTOR = _FIREBIRDLOGENTRY,
  __module__ = 'saturnin.micro.fblog.fblog_pb2'
  # @@protoc_insertion_point(class_scope:saturnin.protobuf.FirebirdLogEntry)
  ))
_sym_db.RegisterMessage(FirebirdLogEntry)


# @@protoc_insertion_point(module_scope)