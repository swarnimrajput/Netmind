from flask import Flask, request, jsonify
import subprocess
import logging
import json

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/netbox-webhook', methods=['POST'])
def netbox_webhook():
    """Handle NetBox webhooks and trigger Ansible playbooks"""
    
    data = request.json
    event_type = data.get('event')
    model = data.get('model')
    
    logging.info(f"Received webhook: {event_type} for {model}")
    logging.info(f"Webhook data: {json.dumps(data, indent=2)}")
    
    # Handle device changes
    if model == 'dcim.device' and event_type in ['created', 'updated']:
        device_name = data.get('data', {}).get('name')
        
        try:
            # Trigger configuration push for updated device
            result = subprocess.run([
                'ansible-playbook', 
                '-i', 'netbox_inventory.yml',
                'playbooks/push_configs.yml',
                '--limit', device_name
            ], capture_output=True, text=True, cwd='/Users/swarnimrajput/Netmind/ansible')
            
            if result.returncode == 0:
                return jsonify({
                    "status": "success", 
                    "message": f"Configuration updated for {device_name}",
                    "output": result.stdout
                })
            else:
                return jsonify({
                    "status": "error", 
                    "message": result.stderr
                })
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    
    # Handle interface changes
    elif model == 'dcim.interface' and event_type == 'updated':
        device_name = data.get('data', {}).get('device', {}).get('name')
        interface_name = data.get('data', {}).get('name')
        
        logging.info(f"Interface {interface_name} updated on {device_name}")
        
        # Trigger interface-specific playbook
        try:
            result = subprocess.run([
                'ansible-playbook',
                '-i', 'netbox_inventory.yml', 
                'playbooks/update_interfaces.yml',
                '--limit', device_name,
                '--extra-vars', f'interface_name={interface_name}'
            ], capture_output=True, text=True, cwd='/path/to/your/ansible')
            
            return jsonify({"status": "success", "message": f"Interface {interface_name} updated"})
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    
    return jsonify({"status": "ignored", "message": "Event not handled"})

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "NetBox Webhook Server"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
