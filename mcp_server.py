import subprocess
import platform
import shutil
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
import asyncssh

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
async def connect_ssh(host: str, username: str, password: str) -> str:
    """Connect to a server via SSH and store the session globally"""
    global ssh_session
    try:
        ssh_session = await asyncssh.connect(host, username=username, password=password)
        return f"SSH connection to {host} established successfully."
    except Exception as e:
        ssh_session = None
        return f"Failed to connect: {e}"
    
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


if __name__ == "__main__":
    print("Starting MCP server...")
    mcp.run()