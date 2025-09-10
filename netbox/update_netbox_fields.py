import pynetbox

NETBOX_URL = "http://localhost:8000"
API_TOKEN = "c316eac1941ee8fdd5059e4f9e777648459ab551"

# Extended device configurations
DEVICE_CONFIGS = {
    "Router-1": {
        "bgp_asn": "65001",
        "loopback_ip": "1.1.1.1/32",
        "ospf_area": "0",
        "ospf_router_id": "1.1.1.1"
    },
    "Router-2": {
        "bgp_asn": "65002", 
        "loopback_ip": "2.2.2.2/32",
        "ospf_area": "0",
        "ospf_router_id": "2.2.2.2"
    },
    "Router-3": {
        "bgp_asn": "65003",
        "loopback_ip": "3.3.3.3/32", 
        "ospf_area": "0",
        "ospf_router_id": "3.3.3.3"
    }
}

def main():
    nb = pynetbox.api(NETBOX_URL, token=API_TOKEN)
    
    print("[*] Updating device configuration fields in NetBox...")
    
    for device_name, config in DEVICE_CONFIGS.items():
        device = nb.dcim.devices.get(name=device_name)
        if device:
            # Get existing custom fields and merge with new ones
            current_fields = device.custom_fields.copy() if device.custom_fields else {}
            current_fields.update(config)
            
            device.update({"custom_fields": current_fields})
            print(f"[+] Updated {device_name} with config: {config}")
        else:
            print(f"[!] Device {device_name} not found!")
    
    print("[*] Configuration field updates completed!")

if __name__ == "__main__":
    main()
