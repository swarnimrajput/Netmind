#!/usr/bin/env python3
"""
Device State Validation Script - Fixed for Container IPs
"""

import json
import sys
import os
import re
import requests
import subprocess
from datetime import datetime
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import concurrent.futures
import threading

# Configuration
NETBOX_URL = "http://localhost:8000"
API_TOKEN = "c316eac1941ee8fdd5059e4f9e777648459ab551"

class DeviceValidator:
    def __init__(self):
        self.netbox_url = NETBOX_URL
        self.api_token = API_TOKEN
        self.headers = {
            'Authorization': f'Token {self.api_token}',
            'Content-Type': 'application/json'
        }
        self.results = {}
        self.lock = threading.Lock()
        
        # Get container IPs dynamically
        self.device_mapping = self.get_container_mappings()
    
    def get_container_mappings(self):
        """Get container IP addresses dynamically"""
        device_mapping = {}
        
        containers = ['R1', 'R2', 'R3']
        device_names = ['Router-1', 'Router-2', 'Router-3']
        
        for i, container_name in enumerate(containers):
            try:
                # Get container IP
                result = subprocess.run([
                    'docker', 'inspect', '-f', 
                    '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', 
                    container_name
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and result.stdout.strip():
                    container_ip = result.stdout.strip()
                    device_mapping[device_names[i]] = {
                        'container': container_name,
                        'ip': container_ip,
                        'connection_type': 'ssh'
                    }
                    print(f"📍 {device_names[i]} -> {container_name} ({container_ip})")
                else:
                    # Fallback to container name
                    device_mapping[device_names[i]] = {
                        'container': container_name,
                        'ip': container_name,
                        'connection_type': 'docker_exec'
                    }
                    print(f"📍 {device_names[i]} -> {container_name} (docker exec)")
                    
            except Exception as e:
                print(f"⚠️ Could not get IP for {container_name}: {e}")
                # Use docker exec as fallback
                device_mapping[device_names[i]] = {
                    'container': container_name,
                    'ip': container_name,
                    'connection_type': 'docker_exec'
                }
        
        return device_mapping
    
    def get_netbox_devices(self):
        """Fetch all devices from NetBox"""
        try:
            response = requests.get(
                f"{self.netbox_url}/api/dcim/devices/",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()['results']
        except Exception as e:
            print(f"❌ Error fetching NetBox devices: {e}")
            return []
    
    def get_netbox_device_state(self, device_name):
        """Get intended state from NetBox for a specific device"""
        try:
            response = requests.get(
                f"{self.netbox_url}/api/dcim/devices/?name={device_name}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            devices = response.json()['results']
            
            if not devices:
                return None
                
            device = devices[0]
            
            # Extract intended state
            intended_state = {
                'device_name': device['name'],
                'bgp_asn': device.get('custom_fields', {}).get('bgp_asn', 'Unknown'),
                'loopback_ip': device.get('custom_fields', {}).get('loopback_ip', 'Unknown'),
                'ospf_router_id': device.get('custom_fields', {}).get('ospf_router_id', 'Unknown'),
                'ospf_area': device.get('custom_fields', {}).get('ospf_area', '0'),
                'primary_ip': str(device.get('primary_ip4', {}).get('address', 'Unknown')) if device.get('primary_ip4') else 'Unknown'
            }
            
            return intended_state
            
        except Exception as e:
            print(f"❌ Error fetching NetBox state for {device_name}: {e}")
            return None
    
    def get_device_connection_params(self, device_name):
        """Get connection parameters for device"""
        device_info = self.device_mapping.get(device_name)
        if not device_info:
            return None
        
        if device_info['connection_type'] == 'ssh':
            return {
                'device_type': 'linux',
                'host': device_info['ip'],
                'username': 'root',
                'password': 'cisco123',
                'timeout': 20,
                'session_timeout': 60
            }
        else:
            return {
                'device_type': 'linux',
                'host': device_info['container'],
                'username': 'root',
                'password': 'cisco123',
                'timeout': 20,
                'session_timeout': 60
            }
    
    def execute_docker_command(self, container_name, command):
        """Execute command in Docker container directly"""
        try:
            result = subprocess.run([
                'docker', 'exec', container_name, 'sh', '-c', command
            ], capture_output=True, text=True, timeout=30)
            
            return result.stdout if result.returncode == 0 else result.stderr
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def get_device_actual_state_docker(self, device_name):
        """Get device state using docker exec (fallback method)"""
        device_info = self.device_mapping.get(device_name)
        container_name = device_info['container']
        
        try:
            print(f"🔍 Connecting to {device_name} via docker exec...")
            
            # Get interface information
            interfaces_output = self.execute_docker_command(container_name, 'ip addr show')
            interfaces = self.parse_interface_output(interfaces_output)
            
            # Try to get BGP info (mock for now)
            bgp_info = {
                'bgp_asn': device_info.get('expected_bgp_asn', 'Unknown'),
                'bgp_router_id': 'Unknown'
            }
            
            # Extract loopback IP
            loopback_ip = 'Unknown'
            if 'lo' in interfaces and interfaces['lo']['addresses']:
                loopback_ip = interfaces['lo']['addresses'][0]
            
            actual_state = {
                'device_name': device_name,
                'bgp_asn': bgp_info['bgp_asn'],
                'bgp_router_id': bgp_info['bgp_router_id'],
                'loopback_ip': loopback_ip,
                'interfaces': interfaces,
                'connection_status': 'Connected',
                'connection_method': 'docker_exec',
                'collected_at': datetime.now().isoformat()
            }
            
            print(f"✅ Successfully collected state from {device_name} (docker exec)")
            return actual_state
            
        except Exception as e:
            print(f"❌ Error collecting state from {device_name}: {e}")
            return {
                'device_name': device_name,
                'connection_status': 'Failed',
                'connection_method': 'docker_exec',
                'error': str(e),
                'collected_at': datetime.now().isoformat()
            }
    
    def parse_interface_output(self, output):
        """Parse 'ip addr show' output to extract interface information"""
        interfaces = {}
        current_interface = None
        
        for line in output.split('\n'):
            # Match interface line: "1: lo: <LOOPBACK,UP,LOWER_UP>"
            interface_match = re.match(r'^\d+:\s+(\w+):\s+<([^>]+)>', line.strip())
            if interface_match:
                interface_name = interface_match.group(1)
                flags = interface_match.group(2)
                current_interface = interface_name
                interfaces[current_interface] = {
                    'name': interface_name,
                    'status': 'UP' if 'UP' in flags else 'DOWN',
                    'addresses': []
                }
            
            # Match IP address line: "inet 1.1.1.1/32 scope host lo"
            if current_interface and 'inet ' in line:
                ip_match = re.search(r'inet\s+([0-9./]+)', line)
                if ip_match:
                    ip_addr = ip_match.group(1)
                    interfaces[current_interface]['addresses'].append(ip_addr)
        
        return interfaces
    
    def get_device_actual_state(self, device_name, connection_params):
        """Connect to device and get actual state"""
        device_info = self.device_mapping.get(device_name)
        
        # If using docker exec, use that method
        if device_info.get('connection_type') == 'docker_exec':
            return self.get_device_actual_state_docker(device_name)
        
        # Try SSH connection
        try:
            print(f"🔍 Connecting to {device_name} via SSH...")
            
            with ConnectHandler(**connection_params) as conn:
                # Get interface information
                interfaces_output = conn.send_command('ip addr show')
                interfaces = self.parse_interface_output(interfaces_output)
                
                # Mock BGP info for now
                bgp_info = {'bgp_asn': 'Unknown', 'bgp_router_id': 'Unknown'}
                
                # Extract loopback IP
                loopback_ip = 'Unknown'
                if 'lo' in interfaces and interfaces['lo']['addresses']:
                    loopback_ip = interfaces['lo']['addresses'][0]
                
                actual_state = {
                    'device_name': device_name,
                    'bgp_asn': bgp_info['bgp_asn'],
                    'bgp_router_id': bgp_info['bgp_router_id'],
                    'loopback_ip': loopback_ip,
                    'interfaces': interfaces,
                    'connection_status': 'Connected',
                    'connection_method': 'ssh',
                    'collected_at': datetime.now().isoformat()
                }
                
                print(f"✅ Successfully collected state from {device_name}")
                return actual_state
                
        except Exception as e:
            print(f"❌ SSH failed to {device_name}, trying docker exec: {e}")
            # Fallback to docker exec
            return self.get_device_actual_state_docker(device_name)
    
    def compare_device_state(self, device_name, intended, actual):
        """Compare intended vs actual state for a device"""
        if actual.get('connection_status') != 'Connected':
            return {
                'device': device_name,
                'status': 'Unreachable',
                'connection_status': actual.get('connection_status', 'Unknown'),
                'connection_method': actual.get('connection_method', 'Unknown'),
                'error': actual.get('error', 'Unknown error'),
                'checks': {}
            }
        
        checks = {}
        overall_status = 'Passed'
        
        # Interface status check
        lo_interface = actual.get('interfaces', {}).get('lo', {})
        if lo_interface:
            if lo_interface.get('status') == 'UP':
                checks['loopback_interface'] = {'status': 'Up', 'details': lo_interface}
            else:
                checks['loopback_interface'] = {'status': 'Down', 'details': lo_interface}
                overall_status = 'Failed'
        else:
            checks['loopback_interface'] = {'status': 'Not Found', 'details': {}}
        
        # Basic connectivity check
        checks['connectivity'] = {
            'status': 'Connected',
            'method': actual.get('connection_method', 'Unknown')
        }
        
        return {
            'device': device_name,
            'status': overall_status,
            'connection_status': 'Connected',
            'connection_method': actual.get('connection_method', 'Unknown'),
            'checks': checks,
            'intended_state': intended,
            'actual_state': actual,
            'validated_at': datetime.now().isoformat()
        }
    
    def validate_device(self, device_name):
        """Validate a single device"""
        print(f"🎯 Validating {device_name}...")
        
        # Get intended state from NetBox
        intended_state = self.get_netbox_device_state(device_name)
        if not intended_state:
            print(f"❌ Could not get intended state for {device_name}")
            return None
        
        # Get connection parameters
        connection_params = self.get_device_connection_params(device_name)
        if not connection_params:
            print(f"❌ Unknown device mapping for {device_name}")
            return None
        
        # Get actual state from device
        actual_state = self.get_device_actual_state(device_name, connection_params)
        
        # Compare states
        comparison_result = self.compare_device_state(device_name, intended_state, actual_state)
        
        # Thread-safe result storage
        with self.lock:
            self.results[device_name] = comparison_result
        
        return comparison_result
    
    def validate_all_devices(self):
        """Validate all devices in parallel"""
        print("🚀 Starting device state validation...")
        
        # Get devices from NetBox
        netbox_devices = self.get_netbox_devices()
        device_names = [device['name'] for device in netbox_devices if 'Router-' in device['name']]
        
        if not device_names:
            print("❌ No devices found in NetBox")
            return {}
        
        print(f"📋 Found {len(device_names)} devices: {', '.join(device_names)}")
        
        # Validate devices in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.validate_device, device_name): device_name 
                      for device_name in device_names}
            
            for future in concurrent.futures.as_completed(futures):
                device_name = futures[future]
                try:
                    result = future.result()
                    if result:
                        status = result.get('status', 'Unknown')
                        connection_method = result.get('connection_method', 'Unknown')
                        print(f"✅ {device_name}: {status} ({connection_method})")
                    else:
                        print(f"❌ {device_name}: Validation failed")
                except Exception as e:
                    print(f"❌ {device_name}: Exception - {e}")
        
        return self.results
    
    def generate_summary(self):
        """Generate validation summary"""
        if not self.results:
            return "No validation results available"
        
        total_devices = len(self.results)
        passed_devices = len([r for r in self.results.values() if r.get('status') == 'Passed'])
        failed_devices = len([r for r in self.results.values() if r.get('status') == 'Failed'])
        unreachable_devices = len([r for r in self.results.values() if r.get('status') == 'Unreachable'])
        
        summary = f"""
🎯 Device State Validation Summary
==================================
Total Devices: {total_devices}
✅ Passed: {passed_devices}
❌ Failed: {failed_devices}
🔌 Unreachable: {unreachable_devices}

Device Details:
"""
        
        for device_name, result in self.results.items():
            status = result.get('status', 'Unknown')
            connection_method = result.get('connection_method', 'Unknown')
            emoji = '✅' if status == 'Passed' else '❌' if status == 'Failed' else '🔌'
            summary += f"{emoji} {device_name}: {status} ({connection_method})\n"
            
            if result.get('checks'):
                for check_name, check_result in result['checks'].items():
                    check_status = check_result.get('status', 'Unknown')
                    summary += f"   └─ {check_name}: {check_status}\n"
        
        return summary

def main():
    """Main execution function"""
    print("=" * 60)
    print("🎯 Network Device State Validation (Container Fixed)")
    print("=" * 60)
    
    # Initialize validator
    validator = DeviceValidator()
    
    # Run validation
    results = validator.validate_all_devices()
    
    # Generate summary
    summary = validator.generate_summary()
    print(summary)
    
    # Save results to JSON file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"device_validation_{timestamp}.json"
    
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to: {output_file}")
    except Exception as e:
        print(f"❌ Error saving results: {e}")
    
    return results

if __name__ == "__main__":
    results = main()
