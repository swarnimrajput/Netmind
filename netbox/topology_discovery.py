#!/usr/bin/env python3

import pynetbox
import json
import os
import subprocess
from datetime import datetime

# Configuration
NETBOX_URL = os.getenv('NETBOX_URL', 'http://localhost:8000')
API_TOKEN = os.getenv('NETBOX_API_TOKEN', 'c316eac1941ee8fdd5059e4f9e777648459ab551')

def discover_network_topology():
    """Discover network topology from NetBox devices"""
    print("🔍 Discovering network topology...")
    
    try:
        nb = pynetbox.api(NETBOX_URL, token=API_TOKEN)
        devices = nb.dcim.devices.filter(role='router')
        
        topology_data = {
            'nodes': [],
            'connections': [],
            'discovered_at': datetime.now().isoformat()
        }
        
        # Add nodes from NetBox devices
        for device in devices:
            node = {
                'id': device.name,
                'name': device.name,
                'type': 'router',
                'platform': str(device.platform) if device.platform else 'FRRouting',
                'site': str(device.site) if device.site else 'Lab',
                'status': str(device.status),
                'primary_ip': str(device.primary_ip4) if device.primary_ip4 else None
            }
            topology_data['nodes'].append(node)
        
        # Create sample connections between routers
        # In a real environment, you'd discover these via LLDP/CDP
        if len(topology_data['nodes']) >= 3:
            connections = [
                {'source': 'Router-1', 'target': 'Router-2', 'type': 'ethernet'},
                {'source': 'Router-2', 'target': 'Router-3', 'type': 'ethernet'},
                {'source': 'Router-1', 'target': 'Router-3', 'type': 'ethernet'}
            ]
            topology_data['connections'] = connections
        
        print(f"📊 Discovered {len(topology_data['nodes'])} devices with {len(topology_data['connections'])} connections")
        return topology_data
        
    except Exception as e:
        print(f"❌ Error discovering topology: {e}")
        return None

def create_interactive_topology(G, topology_data):
    """Create interactive topology visualization using Plotly"""
    try:
        import plotly.graph_objects as go
        import networkx as nx
        
        print("🎨 Creating interactive topology visualization...")
        
        # Get positions for nodes
        pos = nx.spring_layout(G, k=3, iterations=50)
        
        # Extract edges
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        # Create edge trace
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=2, color='#888'),
            hoverinfo='none',
            mode='lines'
        )
        
        # Extract nodes
        node_x = []
        node_y = []
        node_text = []
        node_info = []
        
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(node)
            
            # Get node info
            node_data = G.nodes[node]
            info_text = f"<b>{node}</b><br>"
            info_text += f"Type: {node_data.get('type', 'Router')}<br>"
            info_text += f"Platform: {node_data.get('platform', 'FRRouting')}<br>"
            info_text += f"Site: {node_data.get('site', 'Lab')}<br>"
            if node_data.get('primary_ip'):
                info_text += f"IP: {node_data['primary_ip']}<br>"
            node_info.append(info_text)
        
        # Create node trace
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=node_text,
            textposition="middle center",
            hovertext=node_info,
            marker=dict(
                size=50,
                color='lightblue',
                line=dict(width=2, color='darkblue')
            )
        )
        
        # Create the figure with corrected syntax
        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title=dict(
                    text='Network Topology Discovery<br>' + 
                         f'<sub>Discovered at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</sub>',
                    x=0.5,
                    font=dict(size=16)
                ),
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                annotations=[
                    dict(
                        text=f"Devices: {len(G.nodes())}<br>Connections: {len(G.edges())}",
                        showarrow=False,
                        xref="paper", yref="paper",
                        x=0.005, y=-0.002,
                        xanchor='left', yanchor='bottom',
                        font=dict(size=12)
                    )
                ],
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor='white',
                height=600,
                width=800
            )
        )
        
        return fig
        
    except ImportError:
        print("❌ Plotly not installed. Install with: pip install plotly")
        return None
    except Exception as e:
        print(f"❌ Error creating interactive topology: {e}")
        return None

def create_networkx_graph(topology_data):
    """Create NetworkX graph from topology data"""
    try:
        import networkx as nx
        
        G = nx.Graph()
        
        # Add nodes
        for node in topology_data['nodes']:
            G.add_node(node['id'], **node)
        
        # Add edges
        for conn in topology_data['connections']:
            G.add_edge(conn['source'], conn['target'], **conn)
        
        return G
        
    except ImportError:
        print("❌ NetworkX not installed. Install with: pip install networkx")
        return None

def save_topology_data(topology_data):
    """Save topology data to JSON file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"topology_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(topology_data, f, indent=2)
    
    print(f"💾 Topology data saved to: {filename}")
    return filename

def main():
    """Main topology discovery function"""
    print("=" * 60)
    print("🌐 Network Topology Discovery & Visualization")
    print("=" * 60)
    
    # Step 1: Discover topology
    topology_data = discover_network_topology()
    if not topology_data:
        print("❌ Failed to discover topology")
        return
    
    # Step 2: Save topology data
    json_file = save_topology_data(topology_data)
    
    # Step 3: Create graph
    G = create_networkx_graph(topology_data)
    if not G:
        print("❌ Failed to create network graph")
        return
    
    # Step 4: Create visualization
    fig = create_interactive_topology(G, topology_data)
    if fig:
        # Save interactive plot
        try:
            import plotly.offline as pyo
            html_file = f"topology_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            pyo.plot(fig, filename=html_file, auto_open=True)
            print(f"🌐 Interactive topology saved to: {html_file}")
        except Exception as e:
            print(f"❌ Failed to save interactive plot: {e}")
    
    # Step 5: Create simple text visualization
    print("\n📋 Network Topology Summary:")
    print("-" * 40)
    for node in topology_data['nodes']:
        print(f"📍 {node['name']} ({node['platform']})")
        if node.get('primary_ip'):
            print(f"   IP: {node['primary_ip']}")
    
    print("\n🔗 Network Connections:")
    print("-" * 40)
    for conn in topology_data['connections']:
        print(f"🔌 {conn['source']} ↔ {conn['target']} ({conn['type']})")
    
    print(f"\n✅ Topology discovery completed!")
    print(f"📊 Found {len(topology_data['nodes'])} devices and {len(topology_data['connections'])} connections")

if __name__ == "__main__":
    main()
