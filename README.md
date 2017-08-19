# trumble

Event-driven Mumble client library for Python 3.6

## How to use

Subclass a class like `trumble.SimpleTrumble` (recommended) or `trumble.TrumbleCore` (hard mode)
and add event handlers with `on_*` methods. These methods are basically `snake_case` versions
of the classes in `trumble.messages`, as well as `on_connect` and `on_disconnect`.
Look at the implementation of `trumble.SimpleTrumble` for examples.

You can send messages to the server by returning or yielding instances of classes
from `trumble.messages`, like `UserStats` or `TextMessage`. The event loop in `TrumbleCore`
can handle basically any kind of method, so you can use `async` or normal functions,
`yield` or `return`, and single messages or iterables of messages.

## Status

What works:
* Receiving/sending control-channel events
* Concurrent event handling with trio
* Simple bot for tracking user and channel state

What doesn't work yet:
* Receiving/sending data-channel events (audio)
* Opus support

What hasn't been tested:
* Client certificates
* Most error conditions (network failure, access denied, etc)

What will probably never work:
* CELT and Speex support
* UDP support
