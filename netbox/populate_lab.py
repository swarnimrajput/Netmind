import pynetbox

# ------------------------------
# CONFIG
# ------------------------------
NETBOX_URL = "http://localhost:8000"
API_TOKEN = "c316eac1941ee8fdd5059e4f9e777648459ab551"   # Get this from NetBox UI → Admin → API Tokens

# Devices to create
LAB_DEVICES = [
    {
        "name": "Router-1",
        "mgmt_ip": "10.0.0.1/24",
        "interfaces": [
            {"name": "Gig0/0", "ip": "10.0.0.1/24"},
            {"name": "Gig0/1", "ip": "192.168.1.1/24"}
        ]
    },
    {
        "name": "Router-2",
        "mgmt_ip": "10.0.0.2/24",
        "interfaces": [
            {"name": "Gig0/0", "ip": "10.0.0.2/24"},
            {"name": "Gig0/1", "ip": "192.168.2.1/24"}
        ]
    },
    {
        "name": "Router-3",
        "mgmt_ip": "10.0.0.3/24",
        "interfaces": [
            {"name": "Gig0/0", "ip": "10.0.0.3/24"},
            {"name": "Gig0/1", "ip": "192.168.3.1/24"}
        ]
    }
]

# ------------------------------
# MAIN SCRIPT
# ------------------------------
def main():
    nb = pynetbox.api(NETBOX_URL, token=API_TOKEN)

    # 1. Create a Site
    site = nb.dcim.sites.get(name="Demo-Site")
    if not site:
        site = nb.dcim.sites.create(name="Demo-Site", slug="demo-site")
        print(f"[+] Created site: {site.name}")

    # 2. Create Manufacturer
    manufacturer = nb.dcim.manufacturers.get(name="Cisco")
    if not manufacturer:
        manufacturer = nb.dcim.manufacturers.create(name="Cisco", slug="cisco")
        print("[+] Created manufacturer: Cisco")

    # 3. Create Device Role
    role = nb.dcim.device_roles.get(name="Router")
    if not role:
        role = nb.dcim.device_roles.create(name="Router", slug="router")
        print("[+] Created device role: Router")

    # 4. Create Device Type
    device_type = nb.dcim.device_types.get(model="IOS-Router")
    if not device_type:
        device_type = nb.dcim.device_types.create(
            manufacturer=manufacturer.id,
            model="IOS-Router",
            slug="ios-router"
        )
        print("[+] Created device type: IOS-Router")

    # 5. Create Devices + Interfaces + IPs
    for dev in LAB_DEVICES:
        device = nb.dcim.devices.get(name=dev["name"])
        if not device:
            device = nb.dcim.devices.create(
                name=dev["name"],
                device_type=device_type.id,
                role=role.id,
                site=site.id
            )
            print(f"[+] Created device: {dev['name']}")

        # Create Interfaces
        for iface in dev["interfaces"]:
            intf = nb.dcim.interfaces.get(device_id=device.id, name=iface["name"])
            if not intf:
                intf = nb.dcim.interfaces.create(
                    device=device.id,
                    name=iface["name"],
                    type="1000base-t"
                )
                print(f"   [+] Added interface: {iface['name']}")

            # Assign IP Address
            ip = nb.ipam.ip_addresses.get(address=iface["ip"])
            if not ip:
                ip = nb.ipam.ip_addresses.create(
                    address=iface["ip"],
                    assigned_object_type="dcim.interface",
                    assigned_object_id=intf.id
                )
                print(f"   [+] Assigned IP: {iface['ip']} to {iface['name']}")

    print("\n✅ Lab population complete!")


if __name__ == "__main__":
    main()
