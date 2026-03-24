"""
Test script — Modbus TCP connection + DI read
"""
from pymodbus.client import ModbusTcpClient

IP       = "10.10.10.10"
PORT     = 502
SLAVE_ID = 1

client = ModbusTcpClient(IP, port=PORT, timeout=3)
connected = client.connect()
print(f"Connect: {connected}")

if not connected:
    print("ERROR: Cannot connect.")
    exit(1)

# Try every combination of address + device_id
for addr in [0, 1]:
    for dev_id in [0, 1]:
        try:
            r = client.read_discrete_inputs(addr, count=8, device_id=dev_id)
            if r.isError():
                print(f"  addr={addr} device_id={dev_id}  -> Modbus error: {r}")
            else:
                bits = list(r.bits[:8])
                print(f"  addr={addr} device_id={dev_id}  -> OK  bits={bits}")
        except Exception as e:
            print(f"  addr={addr} device_id={dev_id}  -> Exception: {e}")

client.close()
