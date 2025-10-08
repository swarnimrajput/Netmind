#!/usr/bin/env python3
"""
Network Device Health Monitoring Script  
Monitors device reachability, container status, and NetBox API connectivity
"""

import json
import subprocess
import socket
import requests
import time
import os
import sys
from datetime import datetime
import concurrent.futures
import threading

# Configuration
NETBOX_URL = "http://localhost:8000"
API_TOKEN = "c316eac1941ee8fdd5059e4f9e777648459ab551"

class NetworkMonitor:
    def __init__(self):
        self.netbox_url = NETBOX_URL
        self.api_token = API_TOKEN
        self.headers = {
            'Authorization': f'Token {self.api_token}',
            'Content-Type': 'application/json'
        }
        self.results = {}
        self.lock = threading.Lock()
        
        # Device mapping - matches your working containers
        self.device_mapping = {
            'Router-1': {'container': 'R1'},
            'Router-2': {'container': 'R2'},
            'Router-3': {'container': 'R3'}
        }
    
    def get_container_ip(self, container_name):
        """Get container IP address"""
        try:
            result = subprocess.run([
                'docker', 'inspect', '-f', 
                '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', 
                container_name
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception:
            return None
    
    def ping_container_ip(self, container_ip, timeout=3):
        """Ping container IP address"""
        try:
            if os.name == 'nt':  # Windows
                cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), container_ip]
            else:  # Unix/Linux/Mac
                cmd = ['ping', '-c', '1', '-W', str(timeout), container_ip]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout + 2
            )
            
            success = result.returncode == 0
            response_time = self.extract_ping_time(result.stdout) if success else None
            
            return {
                'status': 'up' if success else 'down',
                'ip': container_ip,
                'response_time': response_time,
                'details': result.stdout.strip()[:100] if success else 'Ping failed'
            }
        except Exception as e:
            return {
                'status': 'error',
                'ip': container_ip,
                'response_time': None,
                'details': str(e)
            }
    
    def extract_ping_time(self, ping_output):
        """Extract ping response time from output"""
        import re
        time_patterns = [
            r'time[<=](\d+\.?\d*)\s*ms',
            r'time=(\d+\.?\d*)ms',
            r'Average = (\d+)ms'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, ping_output, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None
    
    def docker_container_check(self, container_name):
        """Check if Docker container is running and get detailed status"""
        try:
            # Check if container is running
            result = subprocess.run([
                'docker', 'ps', '--format', 'json', '--filter', f'name={container_name}$'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                # Container is running
                container_info = json.loads(result.stdout.strip())
                
                # Get additional container details
                inspect_result = subprocess.run([
                    'docker', 'inspect', container_name, '--format', '{{json .}}'
                ], capture_output=True, text=True, timeout=10)
                
                container_details = {}
                if inspect_result.returncode == 0:
                    full_info = json.loads(inspect_result.stdout)
                    container_details = {
                        'started_at': full_info['State']['StartedAt'],
                        'status': full_info['State']['Status'],
                        'image': full_info['Config']['Image'],
                        'ip_address': self.get_container_ip(container_name)
                    }
                
                return {
                    'status': 'running',
                    'container_id': container_info.get('ID', 'Unknown')[:12],
                    'image': container_info.get('Image', 'Unknown'),
                    'created': container_info.get('CreatedAt', 'Unknown'),
                    'details': container_details
                }
            else:
                # Check if container exists but is stopped
                all_containers = subprocess.run([
                    'docker', 'ps', '-a', '--format', 'json', '--filter', f'name={container_name}$'
                ], capture_output=True, text=True, timeout=10)
                
                if all_containers.returncode == 0 and all_containers.stdout.strip():
                    container_info = json.loads(all_containers.stdout.strip())
                    return {
                        'status': 'stopped',
                        'container_id': container_info.get('ID', 'Unknown')[:12],
                        'image': container_info.get('Image', 'Unknown'),
                        'details': f'Container exists but is stopped'
                    }
                else:
                    return {
                        'status': 'not_found',
                        'details': f'Container {container_name} does not exist'
                    }
                    
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'details': 'Docker command timeout'
            }
        except json.JSONDecodeError:
            return {
                'status': 'stopped',
                'details': f'Container {container_name} not running'
            }
        except Exception as e:
            return {
                'status': 'error',
                'details': f'Docker check failed: {str(e)}'
            }
    
    def docker_exec_test(self, container_name):
        """Test docker exec functionality"""
        try:
            result = subprocess.run([
                'docker', 'exec', container_name, 'echo', 'Health Check Test'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    'status': 'success',
                    'details': 'Docker exec working normally',
                    'test_output': result.stdout.strip()
                }
            else:
                return {
                    'status': 'failed',
                    'details': f'Docker exec failed: {result.stderr.strip()}'
                }
        except Exception as e:
            return {
                'status': 'error',
                'details': f'Docker exec test error: {str(e)}'
            }
    
    def netbox_api_check(self):
        """Check NetBox API connectivity and status"""
        try:
            start_time = time.time()
            
            # Test API status endpoint
            response = requests.get(
                f"{self.netbox_url}/api/status/",
                headers=self.headers,
                timeout=10
            )
            
            end_time = time.time()
            response.raise_for_status()
            response_data = response.json()
            
            # Test device count query
            devices_response = requests.get(
                f"{self.netbox_url}/api/dcim/devices/?limit=1",
                headers=self.headers,
                timeout=10
            )
            devices_response.raise_for_status()
            device_count = devices_response.json().get('count', 0)
            
            return {
                'status': 'up',
                'response_time': round((end_time - start_time) * 1000, 2),
                'netbox_version': response_data.get('netbox-version', 'Unknown'),
                'device_count': device_count,
                'python_version': response_data.get('python-version', 'Unknown'),
                'details': 'NetBox API is accessible and responding normally'
            }
            
        except requests.exceptions.Timeout:
            return {
                'status': 'timeout',
                'response_time': None,
                'details': 'NetBox API request timeout (>10s)'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'connection_error',
                'response_time': None,
                'details': 'Cannot connect to NetBox API - service may be down'
            }
        except requests.exceptions.HTTPError as e:
            return {
                'status': 'http_error',
                'response_time': None,
                'details': f'NetBox API HTTP error: {e}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'response_time': None,
                'details': f'NetBox API check failed: {str(e)}'
            }
    
    def monitor_device(self, device_name):
        """Monitor a single device comprehensively"""
        print(f"🔍 Monitoring {device_name}...")
        
        device_info = self.device_mapping.get(device_name)
        if not device_info:
            return {
                'device': device_name,
                'status': 'unknown_device',
                'error': 'Device not in monitoring configuration'
            }
        
        container_name = device_info['container']
        
        # Comprehensive monitoring
        monitor_result = {
            'device': device_name,
            'container': container_name,
            'monitored_at': datetime.now().isoformat(),
            'checks': {}
        }
        
        # 1. Docker container status check
        container_check = self.docker_container_check(container_name)
        monitor_result['checks']['container'] = container_check
        
        # 2. Docker exec functionality test
        if container_check['status'] == 'running':
            exec_check = self.docker_exec_test(container_name)
            monitor_result['checks']['docker_exec'] = exec_check
        else:
            monitor_result['checks']['docker_exec'] = {
                'status': 'skipped',
                'details': 'Container not running'
            }
        
        # 3. Ping test (if container has IP)
        container_ip = None
        if container_check['status'] == 'running':
            container_ip = self.get_container_ip(container_name)
            if container_ip:
                ping_check = self.ping_container_ip(container_ip)
                monitor_result['checks']['ping'] = ping_check
            else:
                monitor_result['checks']['ping'] = {
                    'status': 'no_ip',
                    'details': 'Container has no IP address'
                }
        else:
            monitor_result['checks']['ping'] = {
                'status': 'skipped',
                'details': 'Container not running'
            }
        
        # Determine overall device status
        device_up = (
            container_check['status'] == 'running' and
            monitor_result['checks']['docker_exec'].get('status') == 'success'
        )
        
        monitor_result['overall_status'] = 'up' if device_up else 'down'
        monitor_result['container_ip'] = container_ip
        
        # Thread-safe result storage
        with self.lock:
            self.results[device_name] = monitor_result
        
        status_emoji = '✅' if device_up else '❌'
        ip_info = f" ({container_ip})" if container_ip else ""
        print(f"{status_emoji} {device_name}{ip_info}: {monitor_result['overall_status'].upper()}")
        
        return monitor_result
    
    def monitor_infrastructure(self):
        """Monitor NetBox API and overall infrastructure"""
        print("🔍 Monitoring infrastructure...")
        
        infrastructure_result = {
            'monitored_at': datetime.now().isoformat(),
            'checks': {}
        }
        
        # NetBox API check
        netbox_check = self.netbox_api_check()
        infrastructure_result['checks']['netbox_api'] = netbox_check
        
        # Docker system check
        try:
            docker_info = subprocess.run([
                'docker', 'system', 'info', '--format', 'json'
            ], capture_output=True, text=True, timeout=10)
            
            if docker_info.returncode == 0:
                docker_data = json.loads(docker_info.stdout)
                infrastructure_result['checks']['docker_system'] = {
                    'status': 'up',
                    'containers_running': docker_data.get('ContainersRunning', 0),
                    'containers_total': docker_data.get('Containers', 0),
                    'images': docker_data.get('Images', 0),
                    'server_version': docker_data.get('ServerVersion', 'Unknown')
                }
            else:
                infrastructure_result['checks']['docker_system'] = {
                    'status': 'error',
                    'details': 'Docker system info failed'
                }
        except Exception as e:
            infrastructure_result['checks']['docker_system'] = {
                'status': 'error',
                'details': f'Docker system check failed: {str(e)}'
            }
        
        # Overall infrastructure status
        infra_up = (
            netbox_check['status'] == 'up' and
            infrastructure_result['checks']['docker_system']['status'] == 'up'
        )
        infrastructure_result['overall_status'] = 'up' if infra_up else 'down'
        
        with self.lock:
            self.results['infrastructure'] = infrastructure_result
        
        status_emoji = '✅' if infra_up else '❌'
        print(f"{status_emoji} Infrastructure: {infrastructure_result['overall_status'].upper()}")
        
        return infrastructure_result
    
    def monitor_all(self):
        """Monitor all devices and infrastructure"""
        print("🚀 Starting comprehensive network health monitoring...")
        
        device_names = list(self.device_mapping.keys())
        print(f"📋 Monitoring {len(device_names)} devices: {', '.join(device_names)}")
        
        # Monitor infrastructure first
        self.monitor_infrastructure()
        
        # Monitor devices in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.monitor_device, device_name): device_name 
                      for device_name in device_names}
            
            for future in concurrent.futures.as_completed(futures):
                device_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ Error monitoring {device_name}: {e}")
        
        return self.results
    
    def generate_health_summary(self):
        """Generate comprehensive health summary"""
        if not self.results:
            return "No monitoring results available"
        
        # Separate infrastructure and devices
        infrastructure = self.results.get('infrastructure', {})
        devices = {k: v for k, v in self.results.items() if k != 'infrastructure'}
        
        total_devices = len(devices)
        up_devices = len([d for d in devices.values() if d.get('overall_status') == 'up'])
        down_devices = total_devices - up_devices
        
        # Infrastructure status
        netbox_status = infrastructure.get('checks', {}).get('netbox_api', {}).get('status', 'unknown')
        docker_status = infrastructure.get('checks', {}).get('docker_system', {}).get('status', 'unknown')
        
        summary = f"""
🏥 Network Health Monitoring Report
===================================
Monitoring Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Infrastructure Status:
🌐 NetBox API: {netbox_status.upper()}
🐳 Docker System: {docker_status.upper()}

Device Summary:
📊 Total Devices: {total_devices}
✅ Up: {up_devices}
❌ Down: {down_devices}
📈 Health Rate: {(up_devices/total_devices*100):.1f}% if total_devices > 0 else 0

Device Details:
"""
        
        for device_name, result in devices.items():
            status = result.get('overall_status', 'unknown')
            container_ip = result.get('container_ip', 'No IP')
            emoji = '✅' if status == 'up' else '❌'
            summary += f"{emoji} {device_name} ({container_ip}): {status.upper()}\n"
            
            # Add check details
            checks = result.get('checks', {})
            for check_name, check_result in checks.items():
                check_status = check_result.get('status', 'unknown')
                if check_status in ['running', 'success', 'up']:
                    check_emoji = '✅'
                elif check_status in ['skipped', 'no_ip']:
                    check_emoji = '⏭️'
                else:
                    check_emoji = '❌'
                summary += f"   └─ {check_name}: {check_emoji} {check_status}\n"
        
        # Add infrastructure details
        if infrastructure:
            summary += f"\nInfrastructure Details:\n"
            netbox_api = infrastructure.get('checks', {}).get('netbox_api', {})
            if netbox_api:
                version = netbox_api.get('netbox_version', 'Unknown')
                device_count = netbox_api.get('device_count', 0)
                response_time = netbox_api.get('response_time', 0)
                summary += f"   🌐 NetBox {version} - {device_count} devices ({response_time}ms)\n"
            
            docker_sys = infrastructure.get('checks', {}).get('docker_system', {})
            if docker_sys.get('status') == 'up':
                containers_running = docker_sys.get('containers_running', 0)
                containers_total = docker_sys.get('containers_total', 0)
                summary += f"   🐳 Docker: {containers_running}/{containers_total} containers running\n"
        
        return summary
    
    def save_results(self, filename=None):
        """Save monitoring results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"health_monitoring_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            print(f"💾 Health report saved to: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Error saving health report: {e}")
            return None

def main():
    """Main execution function"""
    print("=" * 60)
    print("🏥 Network Device Health Monitor")
    print("=" * 60)
    
    # Initialize monitor
    monitor = NetworkMonitor()
    
    # Run monitoring
    results = monitor.monitor_all()
    
    # Generate and display summary
    summary = monitor.generate_health_summary()
    print(summary)
    
    # Save results
    report_file = monitor.save_results()
    
    # Determine exit code based on results
    devices = {k: v for k, v in results.items() if k != 'infrastructure'}
    infrastructure = results.get('infrastructure', {})
    
    # Check if any critical components are down
    infrastructure_down = infrastructure.get('overall_status') != 'up'
    devices_down = any(device.get('overall_status') != 'up' for device in devices.values())
    
    if infrastructure_down or devices_down:
        print("\n⚠️ Health check detected issues!")
        return 1
    else:
        print("\n✅ All systems healthy!")
        return 0

if __name__ == "__main__":
    result_code = main()
    sys.exit(result_code)
