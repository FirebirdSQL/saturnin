
======================
saturnin.protocol.fbsp
======================

.. automodule:: saturnin.protocol.fbsp
   :no-members:
   :synopsis: Firebird Butler Service Protocol (FBSP)

Constants
=========

.. autodata:: HEADER_FMT_FULL
.. autodata:: HEADER_FMT
.. autodata:: FOURCC
.. autodata:: VERSION_MASK
.. autodata:: ERROR_TYPE_MASK
.. autodata:: PROTO_HELLO
.. autodata:: PROTO_WELCOME
.. autodata:: PROTO_CANCEL_REQ
.. autodata:: PROTO_STATE_INFO
.. autodata:: PROTO_ERROR

Enums
=====

.. autoclass:: MsgType
.. autoclass:: MsgFlag
.. autoclass:: ErrorCode

Classes
=======

.. autoclass:: FBSPMessage
.. autoclass:: HandshakeMessage
.. autoclass:: HelloMessage
.. autoclass:: WelcomeMessage
.. autoclass:: APIMessage
.. autoclass:: StateMessage
.. autoclass:: DataMessage
.. autoclass:: CancelMessage
.. autoclass:: ErrorMessage
.. autoclass:: FBSPSession
.. autoclass:: _FBSP
.. autoclass:: FBSPService
.. autoclass:: FBSPClient
.. autoclass:: FBSPEventClient
.. autoclass:: _APIHandlerChecker

Functions
=========

.. autofunction:: bb2h
.. autofunction:: msg_bytes

