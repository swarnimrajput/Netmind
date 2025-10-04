#!/usr/bin/env python3

import pynetbox
import os
import json
import logging
import subprocess
from datetime import datetime

# Configuration
NETBOX_URL = os.getenv('NETBOX_URL', 'http://localhost:8000')
API_TOKEN = os.getenv('NETBOX_API_TOKEN', 'c316eac1941ee8fdd5059e4f9e777648459ab551')

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_ansible_command():
    """Find the ansible-playbook command"""
    import shutil
    
    # Try to find ansible-playbook in PATH
    ansible_cmd = shutil.which('ansible-playbook')
    if ansible_cmd:
        return ansible_cmd
    
    # Common locations
    common_paths = [
        '/usr/local/bin/ansible-playbook',
        '/opt/homebrew/bin/ansible-playbook',
        os.path.expanduser('~/.local/bin/ansible-playbook')
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return 'ansible-playbook'  # Fallback

def load_device_facts():
    """Load device facts from JSON files"""
    logger.info("Loading device facts from JSON files...")
    
    # Get script directory and navigate to ansible facts
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    facts_dir = os.path.join(project_root, 'ansible', 'playbooks', 'facts')
    
    if not os.path.exists(facts_dir):
        logger.error(f"Facts directory not found: {facts_dir}")
        
        # Try to run facts collection first
        logger.info("Attempting to collect facts...")
        try:
            ansible_dir = os.path.join(project_root, 'ansible')
            if os.path.exists(ansible_dir):
                ansible_cmd = find_ansible_command()
                result = subprocess.run([
                    ansible_cmd,
                    '-i', 'netbox_inventory.yml',
                    'playbooks/frr_facts.yml'
                ], capture_output=True, text=True, cwd=ansible_dir)
                
                if result.returncode == 0:
                    logger.info("Facts collection completed")
                else:
                    logger.error(f"Facts collection failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error running facts collection: {e}")
        
        return None
    
    device_facts = {}
    
    try:
        for filename in os.listdir(facts_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(facts_dir, filename)
                
                with open(file_path, 'r') as f:
                    facts_data = json.load(f)
                    
                # Extract device name from filename
                device_name = filename.replace('_facts.json', '')
                device_facts[device_name] = facts_data
                
                logger.info(f"Loaded facts for {device_name}")
        
        return device_facts
        
    except Exception as e:
        logger.error(f"Error loading facts: {e}")
        return None

def get_netbox_current_data(nb):
    """Retrieve current data from NetBox for comparison"""
    logger.info("Retrieving current NetBox data...")
    netbox_data = {}
    
    try:
        devices = nb.dcim.devices.filter(role='router')
        for device in devices:
            device_data = {
                'serial': device.serial,
                'software_version': device.custom_fields.get('software_version'),
                'primary_ip': str(device.primary_ip4) if device.primary_ip4 else None
            }
            
            netbox_data[device.name] = device_data
            
        logger.info(f"Retrieved NetBox data for {len(netbox_data)} devices")
        return netbox_data
        
    except Exception as e:
        logger.error(f"Error retrieving NetBox data: {e}")
        return None

def main():
    """Main execution function"""
    print("=" * 60)
    print("NetBox Source of Truth Round-Trip Sync")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Load device facts
    logger.info("Step 1: Loading device facts...")
    device_facts = load_device_facts()
    
    if not device_facts:
        logger.error("No device facts available")
        return
    
    print(f"✅ Loaded facts from {len(device_facts)} devices")
    
    # Step 2: Connect to NetBox
    logger.info("Step 2: Connecting to NetBox...")
    try:
        nb = pynetbox.api(NETBOX_URL, token=API_TOKEN)
        netbox_data = get_netbox_current_data(nb)
        
        if netbox_data:
            print(f"✅ Retrieved NetBox data for {len(netbox_data)} devices")
        else:
            print("⚠️ Could not retrieve NetBox data")
            
    except Exception as e:
        logger.error(f"Failed to connect to NetBox: {e}")
        print("❌ NetBox connection failed")
        return
    
    print("✅ NetBox sync test completed")

if __name__ == "__main__":
    main()
