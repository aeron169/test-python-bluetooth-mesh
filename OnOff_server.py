#!/usr/bin/env python3
import sys
import asyncio
from contextlib import suppress
import logging
import secrets
from enum import IntEnum

sys.path.append('bluetooth_mesh')
from bluetooth_mesh.application import Application, Element
from bluetooth_mesh.crypto import ApplicationKey, DeviceKey, NetworkKey
from bluetooth_mesh.messages.config import GATTNamespaceDescriptor, StatusCode
from bluetooth_mesh.messages.generic.onoff import GenericOnOffOpcode
from bluetooth_mesh.models.base import Model
from bluetooth_mesh.models import ConfigServer, GenericOnOffServer
from bluetooth_mesh.tokenring import TokenRing

logging.basicConfig(level=logging.INFO)

class GenericOnOffServerHandler(GenericOnOffServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app_message_callbacks[GenericOnOffOpcode.GENERIC_ONOFF_GET].add(self.on_get_light_status)
        self.app_message_callbacks[GenericOnOffOpcode.GENERIC_ONOFF_SET].add(self.on_set_light_status)
        self.app_message_callbacks[GenericOnOffOpcode.GENERIC_ONOFF_SET_UNACKNOWLEDGED].add(self.on_set_light_status_unacknowledged)

    light_status = 0

    def on_get_light_status(
        self,
        _source,
        _app_index,
        _destination,
        message,
    ) -> None:
        print('[On get light status] Sending response')
        loop = asyncio.get_running_loop()
        loop.create_task(self.send_app(
            _source,
            app_index=_app_index,
            opcode=GenericOnOffOpcode.GENERIC_ONOFF_STATUS,
            params={
                'present_onoff': self.light_status,
            },
        ))
    
    def on_set_light_status(
        self,
        _source,
        _app_index,
        _destination,
        message,
    ) -> None:
        print('[On set light status] Changing light status and sending response')
        self.light_status = message.generic_onoff_set.onoff
        self.send_app(
            _destination,
            _app_index,
            _source,
            params={
                'present_onoff': self.light_status,
            },
        )
    
    def on_set_light_status_unacknowledged(
        self,
        _source,
        _app_index,
        _destination,
        message,
    ) -> None:
        self.light_status = message.generic_onoff_set_unacknowledged.onoff
        print('[ON_SET_LIGHT_STATUS_UNACKNOWLEDGED] Changed light status to: ', self.light_status)
        

class meshApp(Application):

    def __init__(self, loop, addr):
        super().__init__(loop)

    async def run(self):
        async with self:
            print('Starting app')

class MainElement(Element):
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        ConfigServer,
        GenericOnOffServerHandler,
    ]


class SampleApplication(Application):
    COMPANY_ID = 0x0136  # Silvair
    PRODUCT_ID = 1
    VERSION_ID = 1
    ELEMENTS = {
        0: MainElement,
    }
    CRPL = 32768
    PATH = "/com/silvair/sample"

    def __init__(self, loop):
        super().__init__(loop)
        self.address = 0x0002

    @property
    def dev_key(self):
        return DeviceKey(bytes.fromhex(secrets.token_hex(16)))

    @property
    def primary_net_key(self):
        return 0, NetworkKey(bytes.fromhex('4696cead19afc4c876677e18bfcf6522'))

    @property
    def app_keys(self):
        return {0: ApplicationKey(secrets.token_bytes(16))}

    # async def configure(self):

        # print('Configuring node...')
        # # client = self.elements[0][ConfigClient]

        # status = await client.bind_app_key(
        #     self.address, net_index=0,
        #     element_address=self.address,
        #     app_key_index=0,
        #     model=GenericOnOffClient
        # )

        # status = await client.bind_app_key(
        #     self.address, net_index=0,
        #     element_address=self.address,
        #     app_key_index=0,
        #     model=GenericOnOffServerHandler
        # )
    

    async def run(self):
        async with self:
            # self.uuid = '00000000-0000-1000-8000-00805f9b34fb'
            self.logger.info('Connecting with address: %s, and token: %x', self.address, self.token_ring.token)
            # await self.connect()
            # await self.configure()

            print('Starting app')
            # client = self.elements[0][GenericOnOffClient]
            server = self.elements[0][GenericOnOffServerHandler]
            await self.join()

            while True:
                await asyncio.sleep(1)
                print('Light status: ', server.light_status)
            # status = await client.set_onoff_unack(self.address, 0, onoff=1, retransmissions=1)
            # await asyncio.sleep(1)
            # status = await client.get_light_status([self.address], 0)
            # print('Light status: ', status)
            # await asyncio.sleep(2)
            # status = await client.set_onoff_unack(self.address, 0, onoff=0, retransmissions=1)
            # await asyncio.sleep(1)
            # status = await client.get_light_status([self.address], 0)
            # print('Light status: ', status)
            

            

def main():
    
    loop = asyncio.get_event_loop()
    app = SampleApplication(loop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(app.run())

if __name__ == '__main__':
    main()