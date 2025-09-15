import pynetbox
import subprocess
import json
import logging
import os

NETBOX_URL = "http://localhost:8000"
API_TOKEN = "c316eac1941ee8fdd5059e4f9e777648459ab551"  # Replace with your actual token

def gather_device_facts():
    """Run Ansible to gather current device facts"""
    logging.info("Running Ansible playbook to gather device facts...")
    
    # Set correct working directory for Ansible
    ansible_dir = os.path.join(os.path.dirname(os.getcwd()), 'ansible')
    
    result = subprocess.run([
        'ansible-playbook',
        '-i', 'netbox_inventory.yml',
        'playbooks/frr_facts.yml',
        '--extra-vars', 'fact_output=json'
    ], capture_output=True, text=True, cwd=ansible_dir)
    
    if result.returncode != 0:
        logging.error(f"Ansible playbook failed: {result.stderr}")
        return {}
    
    logging.info("Ansible playbook completed successfully")
    
    # Look for JSON facts files in ansible/playbooks/facts directory
    facts_data = {}
    facts_dir = os.path.join(ansible_dir, 'playbooks', 'facts')  # ✅ Fixed path!
    
    if os.path.exists(facts_dir):
        logging.info(f"Reading facts from: {facts_dir}")
        for filename in os.listdir(facts_dir):
            if filename.endswith("_facts.json"):
                device_name = filename.replace("_facts.json", "")
                filepath = os.path.join(facts_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        device_facts = json.load(f)
                        facts_data[device_name] = device_facts
                        logging.info(f"Loaded facts for {device_name}")
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON for {device_name}: {e}")
                except Exception as e:
                    logging.error(f"Error reading {filepath}: {e}")
    else:
        logging.error(f"Facts directory not found: {facts_dir}")
    
    return facts_data


def sync_facts_to_netbox(facts_data):
    """Update NetBox with actual device information"""
    nb = pynetbox.api(NETBOX_URL, token=API_TOKEN)
    
    for device_name, device_facts in facts_data.items():
        logging.info(f"Syncing facts for {device_name}")
        device = nb.dcim.devices.get(name=device_name)
        
        if device:
            updated = False
            
            # Update software version if available
            if 'version' in device_facts and device_facts['version']:
                current_fields = device.custom_fields.copy() if device.custom_fields else {}
                current_fields['software_version'] = device_facts['version']
                device.update({"custom_fields": current_fields})
                updated = True
                logging.info(f"Updated software version for {device_name}: {device_facts['version']}")
            
            # Update serial number if available
            if 'serial' in device_facts and device_facts['serial']:
                device.serial = device_facts['serial']
                updated = True
                logging.info(f"Updated serial for {device_name}: {device_facts['serial']}")
            
            if updated:
                device.save()
                logging.info(f"[+] Saved updates to NetBox for {device_name}")
            else:
                logging.info(f"[=] No updates needed for {device_name}")
        else:
            logging.warning(f"[!] Device {device_name} not found in NetBox")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    print("[*] Starting Source of Truth round-trip sync...")
    
    facts = gather_device_facts()
    
    if facts:
        print(f"[*] Found facts for {len(facts)} devices")
        sync_facts_to_netbox(facts)
        print("[*] Sync completed successfully!")
    else:
        print("[!] No facts data collected. Check Ansible playbook output.")
