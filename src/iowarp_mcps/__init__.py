#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path
import click

# Determine if we're running from development or installed package
MODULE_DIR = Path(__file__).parent

def get_servers_path():
    """Get the path to servers directory (dev or installed)"""
    # First try development path (../../mcps from module)
    dev_path = MODULE_DIR.parent.parent / "mcps"
    if dev_path.exists():
        return dev_path
    
    # Try to find shared data in the installed package
    # When installed via wheel, shared data goes to site-packages/
    # Look for mcps directory in various possible locations
    possible_paths = [
        # Standard site-packages installation
        MODULE_DIR.parent / "mcps",  # ../mcps from module
        # Alternative installation paths
        MODULE_DIR / "mcps",  # ./mcps from module (if included directly)
        # System-wide data directory
        Path(sys.prefix) / "share" / "iowarp-mcps" / "mcps",
        # Local data directory 
        Path.home() / ".local" / "share" / "iowarp-mcps" / "mcps",
    ]
    
    # Try each possible path
    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path
    
    # If none found, check if we're in an isolated environment (like uvx)
    # and try to find the data directory relative to the Python executable
    python_path = Path(sys.executable)
    isolated_paths = [
        # uvx style isolated environment - mcps is at the root level
        python_path.parent.parent / "mcps",
        python_path.parent.parent / "share" / "mcps",
        python_path.parent.parent / "purelib" / "mcps", 
        python_path.parent.parent / "data" / "mcps",
    ]
    
    for path in isolated_paths:
        if path.exists() and path.is_dir():
            return path
    
    # Last resort: return the dev path even if it doesn't exist
    # so the caller can handle the missing directory appropriately
    return dev_path

def auto_discover_mcps():
    """Auto-discover MCP servers from the mcps directory"""
    servers_path = get_servers_path()
    if not servers_path.exists():
        return {}, {}
    
    server_command_map = {}
    dir_name_map = {}
    
    # Scan for directories containing pyproject.toml
    for item in servers_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            pyproject_file = item / "pyproject.toml"
            if pyproject_file.exists():
                # Read pyproject.toml to extract entry point
                try:
                    with open(pyproject_file, 'r') as f:
                        content = f.read()
                    
                    # Simple parsing to find the entry point
                    # Look for lines like: server-name-mcp = "module:main"
                    entry_point = None
                    for line in content.split('\n'):
                        line = line.strip()
                        if '-mcp =' in line and '=' in line:
                            entry_point = line.split('=')[0].strip().strip('"\'')
                            break
                    
                    if entry_point:
                        # Create server name by removing -mcp suffix
                        server_name = entry_point.replace('-mcp', '').lower()
                        # Handle special cases for naming
                        if server_name == 'node-hardware':
                            server_name = 'node-hardware'
                        elif server_name == 'parallel-sort':
                            server_name = 'parallel-sort'
                        
                        server_command_map[server_name] = entry_point
                        dir_name_map[server_name] = item.name
                        
                except Exception as e:
                    # Skip directories that can't be processed
                    continue
    
    return server_command_map, dir_name_map

def list_available_servers():
    """List all available servers"""
    server_command_map, _ = auto_discover_mcps()
    return sorted(server_command_map.keys())

@click.command()
@click.argument('server', required=False)
@click.option('-b', '--branch', help='Git branch to use (for development)')
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def main(server, branch, args):
    """Launch IOWarp MCP servers with isolated dependencies using uvx"""
    
    server_command_map, dir_name_map = auto_discover_mcps()
    
    if not server:
        click.echo("Available servers:")
        for s in sorted(server_command_map.keys()):
            click.echo(f"  - {s}")
        click.echo("\nUsage: uvx iowarp-mcps <server-name>")
        click.echo("   or: iowarp-mcps <server-name> (if installed)")
        return
    
    # Normalize server name to lowercase
    server_lower = server.lower()
    
    if server_lower not in server_command_map:
        click.echo(f"Error: Unknown server '{server}'")
        click.echo(f"Available servers: {', '.join(sorted(server_command_map.keys()))}")
        sys.exit(1)
    
    # Get the entry point command and directory name
    entry_command = server_command_map[server_lower]
    actual_dir = dir_name_map[server_lower]
    
    # Build uvx command
    if branch:
        # Run from git branch
        cmd = [
            "uvx",
            "--from",
            f"git+https://github.com/JaimeCernuda/iowarp-mcps.git@{branch}#subdirectory=mcps/{actual_dir}",
            entry_command
        ]
    else:
        # Run from local path in development mode
        servers_path = get_servers_path()
        server_path = servers_path / actual_dir
        
        if server_path.exists():
            # Development mode - run from local path
            cmd = [
                "uvx",
                "--from",
                str(server_path),
                entry_command
            ]
        else:
            # Not in development, try to run the command directly (if installed)
            cmd = [entry_command]
    
    # Add any additional arguments
    cmd.extend(args)
    
    # Execute the command
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except FileNotFoundError:
        if cmd[0] == "uvx":
            click.echo("Error: uvx not found. Please install uv: https://github.com/astral-sh/uv")
        else:
            click.echo(f"Error: {entry_command} not found. Please install the server package.")
        sys.exit(1)

def cli():
    """Entry point for the CLI"""
    main()

if __name__ == "__main__":
    main()