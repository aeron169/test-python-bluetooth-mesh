# User Guide for the BLE Mesh Project on BlueZ

This guide explains how to use the BLE Mesh project to detect unprovisioned nodes, configure the network, and perform local communication tests.

⚠️ DISCLAIMER: PROVISIONING AND THUS COMMUNICATION WITH OTHER DEVICES IS NOT YET POSSIBLE. THIS PROJECT IS STILL IN THE DEVELOPMENT PHASE !

## 1. Prérequis matériels et logiciels

- Two Linux machines (virtual or physical)
- (If no Bluetooth device > 4.0 is initially available on the machines) Two Bluetooth keys compatible with BLE Mesh
- Python 3.7 or higher installed on both machines
- Pip installer

Install the BLE Mesh daemon and Python library on both machines:

```bash
sudo apt-get install bluez-meshd
pip install bluetooth-mesh=0.8.6
```

## 2. Bluetooth Mesh Configuration

Don't forget to activate your Bluetooth peripheral on both machines. (especially on virtual machines)

```bash
  # Free the Bluetooth device from classic Bluetooth, to use it
  sudo hciconfig hci0 down

  # Démarrez le démon BLE Mesh
  sudo systemctl start bluetooth-mesh.service

  # Vérifiez si le service a démarré correctement
  # It must print something like "Bluetooth Mesh Started" or/and "HCI0 dev removed"
  sudo systemctl status bluetooth-mesh.service

  # Ble mesh precedent configuration is located in the /var/lib/bluetooth/mesh directory
  # You can delete the configuration files to reset the network
  # it contains the network configuration, the application keys, and the nodes configuration
  sudo rm -rf /var/lib/bluetooth/mesh
```

## 3. Exécution du code

```bash
python3 OnOff_Client.py
```

## 4. Code explanation

#### Class MainElement :

Some nodes are more complicated than others and consist of multiple independent parts called elements. Each node has at least one element, known as the primary element, and may have additional elements

This class represents an element in the context of BLE Mesh.
In our case, there is only one element, but it is possible to add others.

Our element contains three models: the Generic OnOff Client model, the Generic OnOff Server model (not really, we will se that later), and the Configuration Client model.
These models are Generic Models, which means that the Bluetooth SIG has defined there behavior in the Bluetooth Mesh specification.

#### Class SampleApplication :

An application can be seen as a collection of elements and the functional part of the node.
It is the main class of the project, and it is the one that will be instantiated and executed.

python-bluetooth-mesh provides a default application class, that we need to extend to configure and control our node.

First we need to create our keys for that we need to implement the getters for the keys and of course the keys need to be consistant and coherent with the previous configuration if we restart the program so in the getters we will give hard-coded keys (TODO: find a way to store the keys in a file and read them from there or read them inside the /var/lib/bluetooth/mesh directory)

here is our getters code:

```python
@property
def dev_key(self):
    return DeviceKey(bytes.fromhex('9cfc5dd76b36902b7da2187bebd45f06'))

@property
def primary_net_key(self):
    return 0, NetworkKey(bytes.fromhex('4696cead19afc4c876677e18bfcf6522'))

@property
def app_keys(self):
    return {0: ApplicationKey(secrets.token_bytes(16))}
```

Then we need to create (send them to the deamon so it link the the key to the node config) and bind the app key to the models we do that in the configure method:

```python
def configure(self):
    self.create_net_key(*self.primary_net_key)
    self.create_app_key(*self.app_keys[0])

    status = await client.bind_app_key(
            self.address, net_index=0,
            element_address=self.address,
            app_key_index=0,
            model=GenericOnOffClient
        )

        status = await client.bind_app_key(
            self.address, net_index=0,
            element_address=self.address,
            app_key_index=0,
            model=GenericOnOffServerHandler
        )
```

Then we need to implement the scan_result, add_node_complete, add_node_failed methods
these can be implemented like you want since they just give information about what is happening in a particular situation

```python
# Called when a new node is detected when scanning
def scan_result(self, result):
    print('Scan result: ', result)

# Called when a node has been successfully added to the network
def add_node_complete(self, result):
    print('Add node complete: ', result)

# Called when a node has failed to be added to the network
def add_node_failed(self, result):
    print('Add node failed: ', result)
```

Finally we need to implement the run method which is the main loop of the application that make us able to control the node , scan or send messages to models

For creating a network and an initial node:

```python
# Create a new network
await self.connect()
```

Here is an example on local communication beetween two models in the same node (the client and the server) :

```python
status = await client.get_light_status([self.address], 0)
print('---> status after get: ', status)

# set the light status to on without getting a response
status = await client.set_onoff_unack(self.address, 0, onoff=not status[1]['present_onoff'], retransmissions=1)

# get the light status
status = await client.get_light_status([self.address], 0)
```

For scanning unprovisioned nodes we use the scan method:

```python
# Scan for unprovisioned nodes for 5 seconds
await self.management_interface.unprovisioned_scan(seconds=5)
```

For adding a node to the network:

```python
# Add a node to the network with the given UUID
self.management_interface.add_node(uuid_to_add)
```

And for adding a node to the network after it has been detected
we use the scan_result method which is called when a new node is detected when scanning
unprovisioned nodes

```python
def scan_result(self, rssi: int, data: bytes, options: dict):

  #remove the useless 2 bytes at the end of the data
  data = data[:-2].hex()
  print(f'Scan result: rssi: {rssi}, uuid: {data}, options: {options}.')
  uuid_to_add = UUID(data)
  print('Adding node: ', uuid_to_add)

  # Add the node to the network
  loop = asyncio.get_running_loop()
  loop.create_task(self.management_interface.add_node(uuid_to_add))
```

we need to wrap the add_node method in a task because the scan_result method is not a coroutine (async function) so we can't use await inside it and we need it for add_node which is a coroutine
