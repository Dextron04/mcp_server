import subprocess
import platform
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
import asyncssh
from dotenv import load_dotenv
import os, sys
import asyncio

load_dotenv()

# print("DEBUG ENV:", os.getenv("USERNAME"), os.getenv("PASSWORD"))

print("ENV DEBUG:", os.getenv("USERNAME"), os.getenv("PASSWORD"), os.getenv("PORT"), file=sys.stderr)


# Initialize MCP server
mcp = FastMCP("Local Server Monitor")

# Global SSH session management
ssh_session = None

# Add a tool to get system information
@mcp.tool()
async def ping_server(address: str) -> str:
    """Ping a server and return the response"""
    if ssh_session:
        try:
            result = await ssh_session.run(f"ping -c 4 {address}", check=True)
            return f"Server: {address}\nStatus: Online\n{result.stdout}"
        except Exception as e:
            return f"Server: {address}\nStatus: Offline\nError: {str(e)}"
    else:
        count = "-n" if platform.system().lower() == "windows" else "-c"
        try:
            output = subprocess.check_output(["ping", count, "4", address], text=True, stderr=subprocess.STDOUT)
            return f"Server: {address}\nStatus: Online\n{output}"
        except subprocess.CalledProcessError as e:
            return f"Server: {address}\nStatus: Offline\nError: {e.output.decode()}"
        
@mcp.tool()
async def run_ssh_command(command: str) -> str:
    """Run a command on the server"""
    if ssh_session is None:
        return "Error: No SSH session established. Please connect to a server first."
    try:
        result = await ssh_session.run(command, check=True)
        return result.stdout
    except Exception as e:
        return f"Error running command: {str(e)}"
    
@mcp.tool()
async def connect_ssh(host: str) -> str:
    """Connect to a server via SSH and store the session globally. Optionally specify a port (default 22)."""
    global ssh_session
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    port = 1444

    if not username or not password:
        return "Error: USERNAME and PASSWORD must be set in environment."

    try:
        ssh_session = await asyncio.wait_for(
        asyncssh.connect(
            host,
            port=port,
            username=username,
            password=password,
            known_hosts=None
        ),
        timeout=10
    )
        return f"SSH connection to {host}:{port} established successfully."
    except asyncssh.PermissionDenied:
        ssh_session = None
        return f"Permission denied for {username}@{host}:{port}. Check credentials."
    except asyncssh.ConnectionLost:
        ssh_session = None
        return f"Lost connection to {host}:{port}. Is the SSH service running?"
    except asyncssh.Error as e:
        ssh_session = None
        return f"SSH error: {str(e)}"
    except Exception as e:
        ssh_session = None
        return f"Unexpected error: {str(e)}"
 
@mcp.prompt()
def list_services_prompt() -> str:
    return "List all running services on the server."
    
    
# Tool to list all running services
@mcp.tool()
async def list_services() -> str:
    if ssh_session:
        try:
            result = await ssh_session.run("systemctl list-units --type=service --state=running", check=True)
            return result.stdout
        except Exception as e:
            return f"Error listing services: {str(e)}"
    else:
        if shutil.which("systemctl"):
            try:
                output = subprocess.check_output(["systemctl", "list-units", "--type=service", "--state=running"], stderr=subprocess.STDOUT)
                return output.decode()
            except subprocess.CalledProcessError as e:
                return f"Error listing services: {e.output.decode()}"
        else:
            try:
                output = subprocess.check_output(["ps", "aux"], text=True, stderr=subprocess.STDOUT)
                return output.decode()
            except subprocess.CalledProcessError as e:
                return f"Error listing services: {e.output.decode()}"
        
# Add a tool to check disk space
@mcp.tool()
async def filesystem_command(command: str, path: str = ".") -> str:
    """Run safe filesystem commands (like ls, du, stat)"""
    allowed = {"ls", "du", "stat", "cat", "find"}
    cmd = command.split()[0]

    if cmd not in allowed:
        return f"Command '{cmd}' is not allowed."

    if ssh_session:
        try:
            result = await ssh_session.run(f"{command} {path}", check=True)
            return result.stdout
        except Exception as e:
            return f"Error running command: {str(e)}"
    else:
        path_obj = Path(path).resolve()
        try:
            output = subprocess.check_output(command.split() + [str(path_obj)], stderr=subprocess.STDOUT)
            return output.decode()
        except subprocess.CalledProcessError as e:
            return f"Error running command: {e.output.decode()}"
    
@mcp.prompt()
def disk_usage_prompt(path: str = "/") -> str:
    return f"Check the disk usage of the directory {path} and summarize the largest files or folders."


@mcp.prompt()
def list_directory_prompt(path: str = ".") -> str:
    return f"List all files and directories inside {path}, including hidden ones."


@mcp.prompt()
def find_file_prompt(filename: str) -> str:
    return f"Find all files named {filename} starting from the root directory."


@mcp.tool()
async def disconnect_ssh() -> str:
    """Disconnect the current SSH session, if any."""
    global ssh_session
    if ssh_session is not None:
        try:
            ssh_session.close()
            await ssh_session.wait_closed()
            ssh_session = None
            return "SSH session disconnected successfully."
        except Exception as e:
            return f"Error disconnecting SSH session: {str(e)}"
    else:
        return "No SSH session to disconnect."


if __name__ == "__main__":
    print("Starting MCP server...")
    mcp.run()