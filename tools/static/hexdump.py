import subprocess
from langchain_core.tools import tool

@tool
def hexdump_tool(binary_path: str, offset: int = 0, length: int = 256) -> str:
    """
    Runs 'hexdump -C' on a binary path to view its raw bytes.
    
    Args:
        binary_path: The absolute path to the binary file.
        offset: The starting offset to read from (default 0).
        length: The number of bytes to read (default 256).
    
    Returns:
        The canonical hex+ASCII output of the 'hexdump' command.
    """
    try:
        # Run hexdump -C -s <offset> -n <length> <path>
        cmd = ["hexdump", "-C", "-s", str(offset), "-n", str(length), binary_path]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
        
        return result.stdout.strip()
    except Exception as e:
        return f"Unexpected error: {str(e)}"