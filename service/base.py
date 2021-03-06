"""
Base class for all services.
"""

import json
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from enum import Enum
import zmq.asyncio
import tornado
from tornado.platform.asyncio import AsyncIOMainLoop


logger = logging.getLogger()
logger.setLevel(logging.INFO)
fh = RotatingFileHandler('services.log', maxBytes=100*1024*1024, backupCount=10)
formatter = logging.Formatter("%(asctime)s - %(name)s:%(lineno)d - %(levelname)s : %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)


class ServiceState(Enum):
    init = 'init'
    starting = 'starting'
    started = 'started'
    stopping = 'stopping'
    stopped = 'stopped'


class ServiceBase():
    """ building block of feed, om, strategy services. """
    def __init__(self, logger_name):
        self.logger = logging.getLogger(logger_name)
        self.state = ServiceState.init
        # service id, and all services should have different sid
        self.sid = 'servicebase'
        self.ctx = zmq.asyncio.Context()
        # REQ client connected to monitor for heartbeating
        self.reqclient = self.ctx.socket(zmq.REQ)
        self.reqclient.connect('tcp://localhost:8810')
        # SUB client for subscribing messages from monitor
        self.subclient = self.ctx.socket(zmq.SUB)
        self.subclient.connect('tcp://localhost:8820')
        self.subclient.setsockopt_string(zmq.SUBSCRIBE, '')

    def _set_state(self, state):
        if state in ServiceState:
            self.state = state
            self.logger.info('set server state to %s', state)
        else:
            self.logger.error('invalid server state, need in ServiceState')
            raise RuntimeError('invalid server state, need in ServiceState')

    async def start(self):
        """ Start service. """
        self._set_state(ServiceState.starting)
        self.logger.info('service starting')
        await self.run()

    async def stop(self):
        """ Stop service. """
        self._set_state(ServiceState.stopped)
        self.logger.info('service stopped')

    def status(self):
        """ Return service state. """
        return self.state.value

    async def pub_msg(self):
        """ For PUB services to publish messages to zmq PUB socket. """

    async def sub_msg(self):
        """ For SUB services to consume messages from subscribed zmq PUBs. """

    async def on_control_msg(self):
        """ Listening from monitor PUB socket for remote control. """
        while True:
            msg = json.loads(await self.subclient.recv_string())
            if msg['sid'] == self.sid:
                if msg['action'] == 'stop':
                    await self.stop()
                elif msg['action'] == 'start':
                    await self.run()

    async def heartbeat(self, infos):
        """ Heartbeat, used to periodically update service status. """
        while True:
            infos.update({'sid': self.sid, 'type': 'heartbeat', 'state': self.state.value})
            await self.reqclient.send_string(json.dumps(infos))
            await self.reqclient.recv_string()
            await asyncio.sleep(10)

    async def run(self):
        """ Where the service does its job, and called by start func. """
        if self.state == ServiceState.started:
            self.logger.error('tried to run service, but state is %s', self.state)
        else:
            self.state = ServiceState.started
            # do nothing here in base class
            # await self.pub_msg()
            # await self.sub_msg()


def start_service(service, infos):
    """ Start service. """
    AsyncIOMainLoop().install()
    loop = tornado.ioloop.IOLoop.current()
    loop.spawn_callback(service.start)
    loop.spawn_callback(service.on_control_msg)
    loop.spawn_callback(service.heartbeat, infos)
    loop.start()


if __name__ == '__main__':
    service = ServiceBase('servicebase')
    start_service(service, {})
