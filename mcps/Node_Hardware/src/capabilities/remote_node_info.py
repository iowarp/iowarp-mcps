"""
Remote Node Information capabilities.
Handles SSH-based remote node information retrieval.
"""
import subprocess
import json
import os
from typing import Dict, Optional, List
from capabilities.system_info import get_system_info
from capabilities.cpu_info import get_cpu_info
from capabilities.memory_info import get_memory_info
from capabilities.disk_info import get_disk_info
from capabilities.network_info import get_network_info
from capabilities.process_info import get_process_info
from capabilities.hardware_summary import get_hardware_summary
from capabilities.gpu_info import get_gpu_info
from capabilities.sensor_info import get_sensor_info


def get_node_info(
    include_filters: Optional[List[str]] = None,
    exclude_filters: Optional[List[str]] = None,
    max_response_size: Optional[int] = None
) -> Dict:
    """
    Get comprehensive local node information with optional filtering and size control.
    
    Args:
        include_filters: List of components to include (e.g., ['cpu', 'memory', 'disk'])
        exclude_filters: List of components to exclude
        max_response_size: Maximum response size in bytes (for token limit control)
        
    Returns:
        Dictionary with filtered node information
    """
    try:
        # Available components with their estimated sizes
        available_components = {
            'system': get_system_info,
            'cpu': get_cpu_info,
            'memory': get_memory_info,
            'disk': get_disk_info,
            'network': get_network_info,
            'processes': get_process_info,
            'hardware_summary': get_hardware_summary,
            'gpu': get_gpu_info,
            'sensors': get_sensor_info
        }
        
        # Component size estimates (in bytes) for token limit control
        component_size_estimates = {
            'system': 2000,
            'cpu': 3000,
            'memory': 1500,
            'disk': 8000,
            'network': 5000,
            'processes': 15000,
            'hardware_summary': 4000,
            'gpu': 2000,
            'sensors': 3000
        }
        
        # Apply filters
        components_to_include = set(available_components.keys())
        
        if include_filters:
            # Validate include filters
            valid_components = set(available_components.keys())
            invalid_components = set(include_filters) - valid_components
            if invalid_components:
                return {
                    'error': f"Invalid components specified: {list(invalid_components)}. Valid components: {list(valid_components)}",
                    'error_type': 'InvalidComponentError',
                    'valid_components': list(valid_components)
                }
            components_to_include = set(include_filters) & valid_components
            
        if exclude_filters:
            # Validate exclude filters
            valid_components = set(available_components.keys())
            invalid_components = set(exclude_filters) - valid_components
            if invalid_components:
                return {
                    'error': f"Invalid components specified for exclusion: {list(invalid_components)}. Valid components: {list(valid_components)}",
                    'error_type': 'InvalidComponentError',
                    'valid_components': list(valid_components)
                }
            components_to_include = components_to_include - set(exclude_filters)
        
        # Size control: if max_response_size is specified, limit components
        if max_response_size:
            estimated_size = sum(component_size_estimates.get(comp, 1000) for comp in components_to_include)
            if estimated_size > max_response_size:
                # Prioritize components by importance
                priority_order = ['system', 'cpu', 'memory', 'hardware_summary', 'disk', 'network', 'gpu', 'sensors', 'processes']
                limited_components = []
                current_size = 0
                
                for comp in priority_order:
                    if comp in components_to_include:
                        comp_size = component_size_estimates.get(comp, 1000)
                        if current_size + comp_size <= max_response_size:
                            limited_components.append(comp)
                            current_size += comp_size
                        else:
                            break
                
                components_to_include = set(limited_components)
        
        # Collect information
        node_info = {}
        errors = []
        collected_components = []
        
        for component in components_to_include:
            try:
                result = available_components[component]()
                node_info[component] = result
                collected_components.append(component)
            except Exception as e:
                errors.append(f"Error getting {component}: {str(e)}")
        
        # Add metadata
        node_info['_metadata'] = {
            'hostname': os.uname().nodename,
            'collection_method': 'local',
            'components_requested': list(components_to_include),
            'components_collected': collected_components,
            'errors': errors,
            'response_size_controlled': max_response_size is not None,
            'total_components_available': len(available_components)
        }
        
        return node_info
        
    except Exception as e:
        return {
            'error': str(e),
            'error_type': type(e).__name__
        }


def get_remote_node_info(
    hostname: str,
    username: Optional[str] = None,
    port: int = 22,
    ssh_key: Optional[str] = None,
    timeout: int = 30,
    include_filters: Optional[List[str]] = None,
    exclude_filters: Optional[List[str]] = None
) -> Dict:
    """
    Get comprehensive remote node information via SSH.
    
    Args:
        hostname: Target hostname or IP address
        username: SSH username (defaults to current user)
        port: SSH port (default 22)
        ssh_key: Path to SSH private key file
        timeout: SSH timeout in seconds
        include_filters: List of components to include (e.g., ['cpu', 'memory', 'disk'])
        exclude_filters: List of components to exclude
        
    Returns:
        Dictionary with remote node information
    """
    try:
        # Get current username if not provided
        if username is None:
            username = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
        
        # Build SSH command
        ssh_cmd = ['ssh']
        
        # Add SSH options
        ssh_cmd.extend([
            '-o', 'ConnectTimeout={}'.format(timeout),
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            '-p', str(port)
        ])
        
        # Add SSH key if provided
        if ssh_key and os.path.exists(ssh_key):
            ssh_cmd.extend(['-i', ssh_key])
        
        # Add user@hostname
        ssh_cmd.append(f'{username}@{hostname}')
        
        # Create the remote script to gather information
        remote_script = _create_remote_info_script(include_filters, exclude_filters)
        
        # Add the command to execute
        ssh_cmd.append(remote_script)
        
        # Execute SSH command
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10  # Add buffer to timeout
        )
        
        if result.returncode == 0:
            # Parse the JSON output
            try:
                remote_info = json.loads(result.stdout)
                
                # Add SSH metadata
                remote_info['_metadata'] = remote_info.get('_metadata', {})
                remote_info['_metadata'].update({
                    'ssh_hostname': hostname,
                    'ssh_username': username,
                    'ssh_port': port,
                    'ssh_key_used': ssh_key is not None,
                    'collection_method': 'remote_ssh',
                    'ssh_timeout': timeout
                })
                
                return remote_info
                
            except json.JSONDecodeError as e:
                return {
                    'error': f"Failed to parse remote output: {str(e)}",
                    'error_type': 'JSONDecodeError',
                    'raw_output': result.stdout,
                    'raw_error': result.stderr
                }
        else:
            return {
                'error': f"SSH command failed with return code {result.returncode}",
                'error_type': 'SSHConnectionError',
                'ssh_error': result.stderr,
                'ssh_output': result.stdout
            }
            
    except subprocess.TimeoutExpired:
        return {
            'error': f"SSH connection to {hostname} timed out after {timeout} seconds",
            'error_type': 'SSHTimeoutError'
        }
    except Exception as e:
        return {
            'error': str(e),
            'error_type': type(e).__name__
        }


def _create_remote_info_script(
    include_filters: Optional[List[str]] = None,
    exclude_filters: Optional[List[str]] = None
) -> str:
    """
    Create a Python script to run on the remote node for information gathering.
    
    Args:
        include_filters: Components to include
        exclude_filters: Components to exclude
        
    Returns:
        Python script as string
    """
    filters_json = json.dumps({
        'include_filters': include_filters,
        'exclude_filters': exclude_filters
    })
    
    script = f'''
import json
import sys
import os
import platform
import subprocess
from datetime import datetime

def safe_run_command(cmd):
    """Safely run a command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None

def get_basic_info():
    """Get basic system information using standard Python libraries."""
    info = {{}}
    
    try:
        # System info
        info['system'] = {{
            'hostname': platform.node(),
            'platform': platform.platform(),
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'current_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }}
        
        # CPU info
        cpu_count = os.cpu_count()
        info['cpu'] = {{
            'logical_cores': cpu_count,
            'architecture': platform.machine(),
            'processor': platform.processor()
        }}
        
        # Memory info (if /proc/meminfo exists)
        if os.path.exists('/proc/meminfo'):
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    info['memory'] = {{
                        'meminfo_available': True,
                        'meminfo_content': meminfo[:1000] + "..." if len(meminfo) > 1000 else meminfo
                    }}
            except:
                info['memory'] = {{'meminfo_available': False}}
        
        # Disk info
        if hasattr(os, 'statvfs'):
            try:
                stat = os.statvfs('/')
                info['disk'] = {{
                    'root_filesystem': {{
                        'total_bytes': stat.f_frsize * stat.f_blocks,
                        'free_bytes': stat.f_frsize * stat.f_bavail,
                        'used_bytes': stat.f_frsize * (stat.f_blocks - stat.f_bavail)
                    }}
                }}
            except:
                info['disk'] = {{'root_filesystem': 'unavailable'}}
        
        # Network info
        hostname_result = safe_run_command('hostname -I')
        if hostname_result:
            info['network'] = {{
                'ip_addresses': hostname_result.split(),
                'hostname': platform.node()
            }}
        
        # Process info
        uptime_result = safe_run_command('uptime')
        if uptime_result:
            info['processes'] = {{
                'uptime': uptime_result
            }}
        
        # Add metadata
        info['_metadata'] = {{
            'hostname': platform.node(),
            'collection_method': 'remote_basic',
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'collection_time': datetime.now().isoformat()
        }}
        
    except Exception as e:
        info['error'] = str(e)
        info['error_type'] = type(e).__name__
    
    return info

# Main execution
try:
    filters = {filters_json}
    node_info = get_basic_info()
    
    # Apply filters if specified
    if filters.get('include_filters'):
        filtered_info = {{}}
        for component in filters['include_filters']:
            if component in node_info:
                filtered_info[component] = node_info[component]
        if '_metadata' in node_info:
            filtered_info['_metadata'] = node_info['_metadata']
        node_info = filtered_info
    
    if filters.get('exclude_filters'):
        for component in filters['exclude_filters']:
            node_info.pop(component, None)
    
    print(json.dumps(node_info, indent=2))
    
except Exception as e:
    print(json.dumps({{
        'error': str(e),
        'error_type': type(e).__name__,
        'collection_method': 'remote_basic'
    }}))
'''
    
    return f"python3 -c '{script}'"


def test_ssh_connection(hostname: str, username: Optional[str] = None, port: int = 22, ssh_key: Optional[str] = None) -> Dict:
    """
    Test SSH connection to a remote host.
    
    Args:
        hostname: Target hostname or IP address
        username: SSH username
        port: SSH port
        ssh_key: Path to SSH private key file
        
    Returns:
        Dictionary with connection test results
    """
    try:
        if username is None:
            username = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
        
        ssh_cmd = ['ssh']
        
        # Add SSH options
        ssh_cmd.extend([
            '-o', 'ConnectTimeout=10',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            '-p', str(port)
        ])
        
        if ssh_key and os.path.exists(ssh_key):
            ssh_cmd.extend(['-i', ssh_key])
        
        ssh_cmd.append(f'{username}@{hostname}')
        ssh_cmd.append('echo "SSH connection successful"')
        
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        return {
            'success': result.returncode == 0,
            'hostname': hostname,
            'username': username,
            'port': port,
            'output': result.stdout,
            'error': result.stderr if result.returncode != 0 else None
        }
        
    except Exception as e:
        return {
            'success': False,
            'hostname': hostname,
            'error': str(e),
            'error_type': type(e).__name__
        } 