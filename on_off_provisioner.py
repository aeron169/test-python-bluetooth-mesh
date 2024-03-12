#!/usr/bin/env python3

'''
This file is a sample application that can be used to test the bluetooth mesh network.
It is a client that can send and get the onoff status of a node.

When launched the node configuration is created in /var/lib/bluetooth/mesh/<uuid> 
so remove it if you want to hard reset the node.

TODO (don't work right now): It can also add a node to the network and configure it since it is a provisioner.
TODO: Create a custom vendor model for our use case
TODO: Connect the program to the interface and the web app
'''

import sys
import asyncio
from contextlib import suppress
import logging
from typing import Tuple

sys.path.append('bluetooth_mesh')
from bluetooth_mesh.application import Application, Element
from bluetooth_mesh.crypto import ApplicationKey, DeviceKey, NetworkKey
from bluetooth_mesh.messages.config import GATTNamespaceDescriptor
from bluetooth_mesh.messages.generic.onoff import GenericOnOffOpcode
from bluetooth_mesh.models import ConfigClient, GenericOnOffServer, GenericOnOffClient
from uuid import UUID

logging.basicConfig(level=logging.INFO)


class GenericOnOffServerHandler(GenericOnOffServer):
    """
    A custom class to handle the GenericOnOffServer model for custom callbacks after receiving a message
    """

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
        """
        Callback function for handling the Generic OnOff Get message.

        Args:
            _source: The source address of the message.
            _app_index: The application index.
            _destination: The destination address of the message.
            message: The message object.

        Returns:
            None
        """
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
        """
        Callback function for handling the Generic OnOff Set message.

        Args:
            _source: The source address of the message.
            _app_index: The application index.
            _destination: The destination address of the message.
            message: The message object.

        Returns:
            None
        """
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
        """
        Callback function for handling the Generic OnOff Set Unacknowledged message.

        Args:
            _source: The source address of the message.
            _app_index: The application index.
            _destination: The destination address of the message.
            message: The message object.

        Returns:
            None
        """
        self.light_status = message.generic_onoff_set_unacknowledged.onoff
        print('[ON_SET_LIGHT_STATUS_UNACKNOWLEDGED] Changed light status to: ', self.light_status)

class MainElement(Element):
    """
    Represents the main element in the Bluetooth mesh network.

    This element is responsible for handling various models such as
    ConfigClient, GenericOnOffClient, and GenericOnOffServerHandler.
    """
    LOCATION = GATTNamespaceDescriptor.MAIN
    MODELS = [
        ConfigClient,
        GenericOnOffClient,
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

    uuid_buffer = []

    def __init__(self, loop):
        super().__init__(loop)
        self.address = 0x0001

    @property
    def dev_key(self):
        return DeviceKey(bytes.fromhex('9cfc5dd76b36902b7da2187bebd45f06'))
    

    @property
    def primary_net_key(self):
        return 0, NetworkKey(bytes.fromhex('4696cead19afc4c876677e18bfcf6522'))

    @property
    def app_keys(self):
        return [(0, 0, ApplicationKey(bytes.fromhex('f2ae98a541ca4f04814da82195bb3dc4')))]
    
    # This function is called when a node has been detected
    def scan_result(self, rssi: int, data: bytes, options: dict):

        #remove the useless 2 bytes at the end of the data
        data = data[:-2].hex()
        print(f'Scan result: rssi: {rssi}, uuid: {data}, options: {options}.')
        uuid_to_add = UUID(data)
        print('Adding node: ', uuid_to_add)

        # Add the node to the network
        loop = asyncio.get_running_loop()
        loop.create_task(self.management_interface.add_node(uuid_to_add))
        

    def request_prov_data(self, count: int) -> Tuple[int, int]:
        print('Requesting prov data')
        return [0, count+1]
    def add_node_complete(self, uuid: bytes, unicast: int, count: int):
        print('Added node: ', uuid, unicast, count)

    def add_node_failed(self, uuid: bytes, reason: str):
        print('Failed to add node: ', uuid, reason)
    
    async def configure(self):
        """
        Configures the node by adding network key, application key, and binding application keys to models.
        """

        print('Configuring node...')
        client = self.elements[0][ConfigClient]

        status = await self.add_net_key(self.primary_net_key[0], self.primary_net_key[1])
        print('Add net key status: ', status)

        status = await self.add_app_key(0, 0, self.app_keys[0][2])
        print('Add app key status: ', status)

        status = await self.bind_app_key(0, self.elements[0][GenericOnOffClient])
        print('Bind app key status: ', status)
        status = await self.bind_app_key(0, self.elements[0][GenericOnOffServerHandler])
        print('Bind app key status: ', status)
    
    async def toggle_local_onoff(self):
        """
        We created a custom function to send and get the local onoff status for testing
        local node (inside the node no communication using the mesh network) communication
        beetween 2 models (GenericOnOffClient and GenericOnOffServerHandler)
        """

        print('Sending and getting local onoff status')
        client = self.elements[0][GenericOnOffClient]

        status = await client.get_light_status([self.address], 0)
        print('---> status after get: ', status)
        
        # set the light status to on without getting a response
        status = await client.set_onoff_unack(self.address, 0, onoff=not status[1]['present_onoff'], retransmissions=1)

        # get the light status
        status = await client.get_light_status([self.address], 0)
        print('---> status after get: ', status)

    async def run(self):
        async with self:
            self.logger.info('Connecting with address: %s, uuid: %s and token: %s', self.address, self.uuid, self.token_ring.token)
            await self.connect()
            await self.configure()

            print('Starting app')
            print(GenericOnOffServerHandler)

            await self.toggle_local_onoff()
            
            await asyncio.sleep(5)
            logging.info('Scanning for unprovisioned devices')

            # the scan_result function is called for each node detected
            await self.management_interface.unprovisioned_scan(seconds=5)

            while True:
                await asyncio.sleep(2)
            

            

def main():
    
    loop = asyncio.get_event_loop()
    app = SampleApplication(loop)

    with suppress(KeyboardInterrupt):
        loop.run_until_complete(app.run())

if __name__ == '__main__':
    main()