import collections
import logging

import trio

from .. import TrumbleCore
from .. import messages


logger = logging.getLogger(__name__)

class SimpleTrumble(TrumbleCore):
    def __init__(self, *args, username='Trumble', password='', access_tokens=None, version=(1, 3, 0), **kwargs):
        super().__init__(*args, **kwargs)
        self.username = username
        self.password = password
        self.access_tokens = access_tokens or []
        self.version = version
        self.sessions = collections.defaultdict(dict)
        self.channels = collections.defaultdict(dict)

        self.buffer = []

    async def on_connect(self):
        """ Immediately after connecting, both client and server exchange version info """
        version = messages.Version()
        version.version = (self.version[0] << 16) + (self.version[1] << 8) + self.version[2]
        return version

    async def on_version(self, message):
        """ After receiving the server's version, we send our authentication data """
        authenticate = messages.Authenticate()
        authenticate.username = self.username
        authenticate.password = self.password
        authenticate.tokens.extend(self.access_tokens)
        authenticate.opus = True
        return authenticate

    async def on_channel_state(self, message):
        """ When a channel is updated, update our list """
        self.channels[message.channel_id].update({
            'name': message.name,
            'parent': message.parent,
        })

    async def on_channel_remove(self, message):
        """ When a channel is removed, remove it from our list """
        if message.channel_id in self.channels:
            del self.channels[message.channel_id]

    async def on_user_state(self, message):
        """ When we connect or a user connects or changes state, we receive their current info """
        if message.session not in self.sessions:
            # if this is the first time we've seen this session,
            # also kick off a query for their "stats" (includes certificate chain)
            # this requires the "Register User" ACL
            user_stats = messages.UserStats()
            user_stats.session = message.session
            yield user_stats
        self.sessions[message.session].update({
            'name': message.name,
            'user_id': message.user_id,
            'channel_id': message.channel_id,
        })

    async def on_user_remove(self, message):
        """ When a user is kicked or disconnects, remove their session """
        del self.sessions[message.session]

    async def on_user_stats(self, message):
        """
        When we query for user stats, we get back a bunch of latency info, but also
        a certificate chain and a boolean indicating whether or not their certificate
        validates with the server's chain. Of course, we can check it ourselves if needed.
        """
        self.sessions[message.session].update({
            'version': (message.version.version >> 16, (message.version.version & 0xff00) >> 8, message.version.version & 0xff),
            'opus': message.opus,
            'certificates': list(message.certificates),
            'strong_certificate': bool(message.certificates and message.strong_certificate),
        })

    async def on_server_sync(self, message):
        """
        After the server finishes sending all users channels on initial connect, this
        event is sent to indicate that the state is now synchronized.
        """
        logger.info('State synchronized, %d channels and %d users', len(self.channels), len(self.sessions))

    async def on_udp_tunnel(self, message):
        if message.type == messages.UDPTunnel.Opus:
            if message.end_transmission:
                logger.info('%s stopped talking', self.sessions[message.session_id]['name'])
