#!/usr/bin/env python3
"""
Network State Dashboard
Real-time visualization of device states and health
"""

import dash
from dash import dcc, html, Input, Output, dash_table
import plotly.graph_objs as go
import plotly.express as px
import json
import pandas as pd
from datetime import datetime
import subprocess
import sys
import os

# Add the scripts directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from validate_device_state import DeviceValidator
    from monitor_devices import NetworkMonitor
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print("Make sure validate_device_state.py and monitor_devices.py are in the same directory")
    sys.exit(1)

# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Network Automation Dashboard"

# Custom CSS styling
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

# Global data store
dashboard_data = {
    'last_update': None,
    'device_states': {},
    'health_status': {},
    'infrastructure_status': {}
}

def get_fresh_data():
    """Collect fresh monitoring and validation data"""
    print("🔄 Collecting fresh data...")
    
    try:
        # Get health monitoring data
        monitor = NetworkMonitor()
        health_results = monitor.monitor_all()
        
        # Get device validation data
        validator = DeviceValidator()
        validation_results = validator.validate_all_devices()
        
        # Update global data store
        dashboard_data['last_update'] = datetime.now()
        dashboard_data['health_status'] = health_results
        dashboard_data['device_states'] = validation_results
        
        print("✅ Data collection completed")
        return True
        
    except Exception as e:
        print(f"❌ Error collecting data: {e}")
        return False

def create_device_status_figure():
    """Create device status overview chart"""
    if not dashboard_data['health_status']:
        return go.Figure().add_annotation(
            text="No data available", 
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font_size=16
        )
    
    devices = {k: v for k, v in dashboard_data['health_status'].items() if k != 'infrastructure'}
    
    device_names = []
    statuses = []
    colors = []
    
    for device_name, device_data in devices.items():
        device_names.append(device_name)
        status = device_data.get('overall_status', 'unknown')
        statuses.append(status.upper())
        
        if status == 'up':
            colors.append('#2ecc71')  # Green
        elif status == 'down':
            colors.append('#e74c3c')  # Red
        else:
            colors.append('#f39c12')  # Orange
    
    fig = go.Figure(data=[
        go.Bar(
            x=device_names,
            y=[1] * len(device_names),
            marker_color=colors,
            text=statuses,
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title="Device Status Overview",
        xaxis_title="Devices",
        yaxis_title="Status",
        showlegend=False,
        height=300,
        yaxis=dict(showticklabels=False)
    )
    
    return fig

def create_validation_summary_figure():
    """Create validation summary pie chart"""
    if not dashboard_data['device_states']:
        return go.Figure().add_annotation(
            text="No validation data available",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font_size=16
        )
    
    status_counts = {'Passed': 0, 'Failed': 0, 'Unreachable': 0}
    
    for device_data in dashboard_data['device_states'].values():
        status = device_data.get('status', 'Unknown')
        if status in status_counts:
            status_counts[status] += 1
    
    fig = go.Figure(data=[
        go.Pie(
            labels=list(status_counts.keys()),
            values=list(status_counts.values()),
            marker_colors=['#2ecc71', '#e74c3c', '#f39c12']
        )
    ])
    
    fig.update_layout(
        title="Device Validation Summary",
        height=300
    )
    
    return fig

def create_device_details_table():
    """Create detailed device information table"""
    if not dashboard_data['health_status'] or not dashboard_data['device_states']:
        return []
    
    table_data = []
    
    devices = {k: v for k, v in dashboard_data['health_status'].items() if k != 'infrastructure'}
    
    for device_name, health_data in devices.items():
        validation_data = dashboard_data['device_states'].get(device_name, {})
        
        # Extract health check results
        checks = health_data.get('checks', {})
        container_status = checks.get('container', {}).get('status', 'Unknown')
        ping_status = checks.get('ping', {}).get('status', 'Unknown')
        ssh_status = checks.get('ssh_login', {}).get('status', 'Unknown')
        
        # Extract validation results
        validation_status = validation_data.get('status', 'Unknown')
        validation_checks = validation_data.get('checks', {})
        
        bgp_status = 'N/A'
        loopback_status = 'N/A'
        
        if validation_checks:
            bgp_check = validation_checks.get('bgp_asn', {})
            bgp_status = bgp_check.get('status', 'N/A')
            
            loopback_check = validation_checks.get('loopback_ip', {})
            loopback_status = loopback_check.get('status', 'N/A')
        
        table_data.append({
            'Device': device_name,
            'Overall Health': health_data.get('overall_status', 'Unknown').upper(),
            'Container': container_status.upper(),
            'Ping': ping_status.upper(),
            'SSH': ssh_status.upper(),
            'Validation': validation_status.upper(),
            'BGP Check': bgp_status.upper(),
            'Loopback Check': loopback_status.upper()
        })
    
    return table_data

def create_infrastructure_status():
    """Create infrastructure status summary"""
    if not dashboard_data['health_status']:
        return html.Div("No infrastructure data available")
    
    infra_data = dashboard_data['health_status'].get('infrastructure', {})
    netbox_check = infra_data.get('checks', {}).get('netbox_api', {})
    
    netbox_status = netbox_check.get('status', 'unknown')
    netbox_version = netbox_check.get('netbox_version', 'Unknown')
    device_count = netbox_check.get('device_count', 0)
    response_time = netbox_check.get('response_time', 0)
    
    status_color = '#2ecc71' if netbox_status == 'up' else '#e74c3c'
    status_emoji = '✅' if netbox_status == 'up' else '❌'
    
    return html.Div([
        html.H4("Infrastructure Status"),
        html.Div([
            html.Span(f"{status_emoji} NetBox API: ", style={'font-weight': 'bold'}),
            html.Span(netbox_status.upper(), style={'color': status_color, 'font-weight': 'bold'})
        ]),
        html.Br(),
        html.Div([
            html.Span("Version: ", style={'font-weight': 'bold'}),
            html.Span(netbox_version)
        ]),
        html.Div([
            html.Span("Device Count: ", style={'font-weight': 'bold'}),
            html.Span(str(device_count))
        ]),
        html.Div([
            html.Span("Response Time: ", style={'font-weight': 'bold'}),
            html.Span(f"{response_time}ms" if response_time else "N/A")
        ])
    ])

# Dashboard Layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("🌐 Network Automation Dashboard", 
                style={'textAlign': 'center', 'color': '#2c3e50', 'marginBottom': 30}),
        html.Div(id='last-update', style={'textAlign': 'center', 'color': '#7f8c8d'})
    ]),
    
    # Auto-refresh interval
    dcc.Interval(
        id='interval-component',
        interval=30*1000,  # Update every 30 seconds
        n_intervals=0
    ),
    
    # Manual refresh button
    html.Div([
        html.Button('🔄 Refresh Now', id='refresh-button', n_clicks=0,
                   style={'margin': '20px auto', 'display': 'block', 'padding': '10px 20px',
                         'backgroundColor': '#3498db', 'color': 'white', 'border': 'none',
                         'borderRadius': '5px', 'cursor': 'pointer'})
    ]),
    
    # Main content area
    html.Div([
        # First row - Status charts
        html.Div([
            html.Div([
                dcc.Graph(id='device-status-chart')
            ], className='six columns'),
            
            html.Div([
                dcc.Graph(id='validation-summary-chart')
            ], className='six columns')
        ], className='row'),
        
        # Second row - Infrastructure and details
        html.Div([
            html.Div([
                html.Div(id='infrastructure-status')
            ], className='four columns'),
            
            html.Div([
                html.H4("Device Details"),
                dash_table.DataTable(
                    id='device-details-table',
                    columns=[
                        {'name': 'Device', 'id': 'Device'},
                        {'name': 'Health', 'id': 'Overall Health'},
                        {'name': 'Container', 'id': 'Container'},
                        {'name': 'Ping', 'id': 'Ping'},
                        {'name': 'SSH', 'id': 'SSH'},
                        {'name': 'Validation', 'id': 'Validation'},
                        {'name': 'BGP', 'id': 'BGP Check'},
                        {'name': 'Loopback', 'id': 'Loopback Check'}
                    ],
                    style_cell={'textAlign': 'center', 'fontSize': '12px'},
                    style_data_conditional=[
                        {
                            'if': {'filter_query': '{Overall Health} = UP'},
                            'backgroundColor': '#d5f4e6',
                            'color': 'black',
                        },
                        {
                            'if': {'filter_query': '{Overall Health} = DOWN'},
                            'backgroundColor': '#fadadd',
                            'color': 'black',
                        }
                    ]
                )
            ], className='eight columns')
        ], className='row', style={'marginTop': 30})
    ], style={'margin': '20px'})
])

# Callbacks
@app.callback(
    [Output('device-status-chart', 'figure'),
     Output('validation-summary-chart', 'figure'),
     Output('infrastructure-status', 'children'),
     Output('device-details-table', 'data'),
     Output('last-update', 'children')],
    [Input('interval-component', 'n_intervals'),
     Input('refresh-button', 'n_clicks')]
)
def update_dashboard(n_intervals, n_clicks):
    """Update all dashboard components"""
    # Refresh data
    get_fresh_data()
    
    # Create updated components
    device_status_fig = create_device_status_figure()
    validation_summary_fig = create_validation_summary_figure()
    infrastructure_status = create_infrastructure_status()
    device_details_data = create_device_details_table()
    
    last_update_text = f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return (device_status_fig, validation_summary_fig, infrastructure_status, 
            device_details_data, last_update_text)

def main():
    """Main function to run dashboard"""
    print("🚀 Starting Network Automation Dashboard...")
    
    # Initial data collection
    success = get_fresh_data()
    if not success:
        print("⚠️ Warning: Could not collect initial data, dashboard will show empty state")
    
    print("🌐 Dashboard available at: http://127.0.0.1:8050")
    print("Press Ctrl+C to stop the dashboard")
    
    # Run the Dash server - UPDATED LINE
    app.run(debug=False, host='127.0.0.1', port=8050)


if __name__ == '__main__':
    main()
