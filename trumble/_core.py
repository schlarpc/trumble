import collections
import inspect
import logging

import trio

from . import messages


logger = logging.getLogger(__name__)

class TrumbleCore:
    """
    `TrumbleCore` implements trio-based connection management, message serialization,
    and event dispatching. On its own, it implements no useful client features besides keep-alives.
    See `SimpleTrumble` for a subclass that implements a client that actually does things.
    """

    def __init__(self, host, port, *, certificate_key_pair=None, verify=True):
        self.host = host
        self.port = port
        self.certificate_key_pair = certificate_key_pair
        self.verify = verify
        self._send_queue = trio.Queue(1024) # TODO why this number?

    async def _connect(self):
        """ Connects to the server and negotiates the TLS connection """
        tcp_stream = await trio.open_tcp_stream(self.host, self.port)
        context = trio.ssl.create_default_context()
        if not self.verify:
            context.check_hostname = False
            context.verify_mode = trio.ssl.CERT_NONE
        if self.certificate_key_pair:
            context.load_cert_chain(*self.certificate_key_pair)
        stream = trio.ssl.SSLStream(tcp_stream, context, server_hostname=self.host)
        await stream.do_handshake()
        return stream

    async def _receive_exactly(self, stream, length):
        """ Reads exactly `length` bytes from `stream` """
        data = bytearray()
        while len(data) < length:
            chunk = await stream.receive_some(length - len(data))
            if not len(chunk):
                # TODO
                raise EOFError('Oops')
            data += chunk
        return bytes(data)

    async def _receive(self, stream):
        """ Receives a message and deserializes it """
        message_id = int.from_bytes(await self._receive_exactly(stream, 2), byteorder='big')
        length = int.from_bytes(await self._receive_exactly(stream, 4), byteorder='big')
        message_data = await self._receive_exactly(stream, length)
        return messages._deserialize(message_id, message_data)

    async def _send(self, stream, message):
        """ Serializes a message and sends it on the given (TCP) stream """
        await stream.send_all(messages._serialize(message))

    async def _get_messages(self, result):
        """
        Recursively unpack iterables, generators, and awaitables
        to produce a stream of messages. The intent is to improve the ergonomics
        of writing Trumble subclasses.
        """
        if inspect.isasyncgen(result):
            async for item in result:
                async for message in self._get_messages(item):
                    yield message
        elif isinstance(result, collections.Iterable):
            for item in result:
                async for message in self._get_messages(item):
                    yield message
        elif inspect.isawaitable(result):
            async for message in self._get_messages(await result):
                yield message
        elif result:
            # TODO check type
            yield result
        else:
            # TODO log
            pass

    async def _dispatch_event(self, event_name, *args, **kwargs):
        """
        Dispatch an event to handlers on this instance, if they exist.
        Handlers can be async or sync, generators or normal methods,
        and can return a message or an iterable of messages
        """
        event_handler_name = 'on_{}'.format(event_name)

        if hasattr(self, event_handler_name):
            logger.debug('Dispatching %s', event_handler_name)
            event_handler = getattr(self, event_handler_name)
            result = event_handler(*args, **kwargs)
            async for message in self._get_messages(result):
                await self.send(message)
        else:
            logger.debug('No handler found for %s', event_handler_name)

    async def _receive_loop(self, nursery, stream):
        """ Receives messages from the server and dispatches the events in coroutines """
        while True:
            message = await self._receive(stream)
            nursery.spawn(self._dispatch_event, messages.get_name_by_class(message.__class__), message)

    async def _send_loop(self, nursery, stream):
        """ Pulls from the outbound queue and sends messages to the server """
        while True:
            message = await self._send_queue.get()
            await self._send(stream, message)

    async def _ping_loop(self):
        """ Send regular Ping messages. Murmur disconnects clients after 30 seconds of no pings. """
        while True:
            await trio.sleep(10)
            ping = messages.Ping()
            await self.send(ping)

    async def send(self, message):
        """ Sends a message to the Mumble server (eventually) """
        await self._send_queue.put(message)

    async def run_async(self):
        """ Start this instance of Trumble in an async context """
        try:
            async with trio.open_nursery() as nursery:
                stream = await self._connect()
                nursery.spawn(self._dispatch_event, 'connect')
                nursery.spawn(self._ping_loop)
                nursery.spawn(self._receive_loop, nursery, stream)
                nursery.spawn(self._send_loop, nursery, stream)
        finally:
            await self._dispatch_event('disconnect')

    def run(self):
        """ Use trio.run to start this instance of Trumble from a sync context """
        trio.run(self.run_async)
