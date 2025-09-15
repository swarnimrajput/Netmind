#!/usr/bin/env python3

import pynetbox
import os
import json
import logging
from datetime import datetime

# Configuration
NETBOX_URL = "http://localhost:8000"
API_TOKEN = "c316eac1941ee8fdd5059e4f9e777648459ab551"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_device_facts():
    """Load device facts from JSON files in ansible/playbooks/facts/"""
    logger.info("Loading device facts from JSON files...")
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Navigate to the correct facts directory: ../ansible/playbooks/facts/
    ansible_dir = os.path.join(os.path.dirname(script_dir), 'ansible')
    facts_dir = os.path.join(ansible_dir, 'playbooks', 'facts')  # ✅ FIXED PATH
    
    if not os.path.exists(facts_dir):
        logger.error(f"Facts directory not found: {facts_dir}")
        return None
    
    device_facts = {}
    
    # Load all JSON files from facts directory
    try:
        for filename in os.listdir(facts_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(facts_dir, filename)
                
                with open(file_path, 'r') as f:
                    facts_data = json.load(f)
                    
                # Extract device name from filename (Router-1_facts.json -> Router-1)
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
                'interfaces': {}
            }
            
            # Get interface IPs - Fixed API call
            interfaces = nb.dcim.interfaces.filter(device_id=device.id)
            for interface in interfaces:
                # Method 1: Try with content type ID (newer NetBox versions)
                try:
                    # Get the content type for dcim.interface
                    content_types = nb.extras.content_types.all()
                    interface_content_type = None
                    for ct in content_types:
                        if ct.model == 'interface' and ct.app_label == 'dcim':
                            interface_content_type = ct.id
                            break
                    
                    if interface_content_type:
                        ip_addresses = nb.ipam.ip_addresses.filter(
                            assigned_object_type=interface_content_type,
                            assigned_object_id=interface.id
                        )
                    else:
                        # Method 2: Alternative approach - get all IPs and filter
                        ip_addresses = []
                        all_ips = nb.ipam.ip_addresses.all()
                        for ip in all_ips:
                            if (hasattr(ip.assigned_object, 'id') and 
                                ip.assigned_object.id == interface.id and
                                hasattr(ip.assigned_object, 'device') and
                                ip.assigned_object.device.id == device.id):
                                ip_addresses.append(ip)
                                
                except Exception as e:
                    logger.debug(f"Content type method failed: {e}")
                    # Method 3: Fallback - iterate through device's assigned IPs
                    ip_addresses = []
                    try:
                        for ip in nb.ipam.ip_addresses.all():
                            if (hasattr(ip, 'assigned_object') and 
                                ip.assigned_object and
                                hasattr(ip.assigned_object, 'name') and
                                ip.assigned_object.name == interface.name and
                                hasattr(ip.assigned_object, 'device') and
                                ip.assigned_object.device.id == device.id):
                                ip_addresses.append(ip)
                    except Exception as fallback_error:
                        logger.debug(f"Fallback method failed: {fallback_error}")
                        ip_addresses = []
                
                if ip_addresses:
                    device_data['interfaces'][interface.name] = str(ip_addresses[0].address)
            
            netbox_data[device.name] = device_data
            
        logger.info(f"Retrieved NetBox data for {len(netbox_data)} devices")
        return netbox_data
        
    except Exception as e:
        logger.error(f"Error retrieving NetBox data: {e}")
        return None


def compare_and_report_differences(netbox_data, device_facts):
    """Compare NetBox data with actual device facts and report differences"""
    logger.info("Comparing NetBox data with device facts...")
    differences = {}
    
    for device_name, facts in device_facts.items():
        device_diffs = {}
        
        # Get corresponding NetBox data
        nb_device_data = netbox_data.get(device_name, {})
        
        # Compare software version
        nb_version = nb_device_data.get('software_version')
        actual_version = facts.get('version')
        if nb_version != actual_version:
            device_diffs['software_version'] = {
                'netbox': nb_version,
                'actual': actual_version
            }
        
        # Compare serial numbers
        nb_serial = nb_device_data.get('serial')
        actual_serial = facts.get('serial')
        if nb_serial != actual_serial:
            device_diffs['serial'] = {
                'netbox': nb_serial,
                'actual': actual_serial
            }
        
        # 🚀 SIMPLIFIED: Skip interface comparison for now
        logger.info(f"Skipping interface comparison for {device_name} (focusing on device-level data)")
            
        if device_diffs:
            differences[device_name] = device_diffs
    
    return differences

def update_netbox_with_facts(nb, device_facts, differences):
    """Update NetBox with actual device information"""
    logger.info("Updating NetBox with device facts...")
    updates_made = 0
    
    for device_name, facts in device_facts.items():
        if device_name not in differences:
            logger.info(f"No differences found for {device_name}, skipping update")
            continue
            
        logger.info(f"Updating NetBox data for {device_name}")
        device = nb.dcim.devices.get(name=device_name)
        
        if not device:
            logger.warning(f"Device {device_name} not found in NetBox")
            continue
        
        device_diffs = differences[device_name]
        
        # Update device serial number if different
        if 'serial' in device_diffs and facts.get('serial'):
            old_serial = device.serial
            device.serial = facts['serial']
            logger.info(f"  Updated serial: {old_serial} -> {facts['serial']}")
            updates_made += 1
        
        # Update software version if different
        if 'software_version' in device_diffs and facts.get('version'):
            old_version = device.custom_fields.get('software_version')
            device.custom_fields['software_version'] = facts['version']
            logger.info(f"  Updated software version: {old_version} -> {facts['version']}")
            updates_made += 1
        
        # Save device updates
        if 'serial' in device_diffs or 'software_version' in device_diffs:
            try:
                device.save()
                logger.info(f"  Successfully saved updates for {device_name}")
            except Exception as e:
                logger.error(f"  Failed to save device {device_name}: {e}")
        
        # 🚀 SIMPLIFIED: Skip interface updates for now
        if 'interfaces' in device_diffs:
            logger.info(f"  Interface updates available for {device_name} (skipped in this version)")
    
    return updates_made


def main():
    """Main execution function"""
    print("=" * 60)
    print("NetBox Source of Truth Round-Trip Sync")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Load device facts from JSON files
    logger.info("Step 1: Loading device facts from JSON files...")
    device_facts = load_device_facts()
    
    if not device_facts:
        logger.error("Failed to load device facts. Please check your facts files.")
        return
    
    print(f"✓ Loaded facts from {len(device_facts)} devices: {list(device_facts.keys())}")
    
    # Step 2: Connect to NetBox
    logger.info("Step 2: Connecting to NetBox...")
    try:
        nb = pynetbox.api(NETBOX_URL, token=API_TOKEN)
        netbox_data = get_netbox_current_data(nb)
        
        if not netbox_data:
            logger.error("Failed to retrieve NetBox data")
            return
            
        print(f"✓ Retrieved NetBox data for {len(netbox_data)} devices: {list(netbox_data.keys())}")
    except Exception as e:
        logger.error(f"Failed to connect to NetBox: {e}")
        return
    
    # Step 3: Compare data and find differences
    logger.info("Step 3: Comparing NetBox data with device facts...")
    differences = compare_and_report_differences(netbox_data, device_facts)
    
    if not differences:
        print("✓ No differences found - NetBox is in sync with devices!")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return
    
    print(f"⚠ Found differences in {len(differences)} devices:")
    for device_name, diffs in differences.items():
        print(f"\n  📍 {device_name}:")
        for field, values in diffs.items():
            if field == 'interfaces':
                for interface, ip_diff in values.items():
                    print(f"    🔌 Interface {interface}: '{ip_diff['netbox']}' -> '{ip_diff['actual']}'")
            else:
                print(f"    🔧 {field}: '{values['netbox']}' -> '{values['actual']}'")
    
    # Step 4: Update NetBox with actual values
    logger.info("Step 4: Updating NetBox with device facts...")
    updates_made = update_netbox_with_facts(nb, device_facts, differences)
    
    print(f"\n🎯 Sync completed! Made {updates_made} updates to NetBox")
    print(f"✅ Source of Truth round-trip completed successfully!")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
