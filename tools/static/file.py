import subprocess
from langchain_core.tools import tool

@tool
def file_tool(binary_path: str) -> str:
    """
    Runs the 'file' command on a binary path to identify its type, architecture, and other metadata.
    
    Args:
        binary_path: The absolute path to the binary file.
    
    Returns:
        The output of the 'file' command or an error message.
    """
    try:
        # Run the 'file' command
        result = subprocess.run(
            ["file", binary_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
        
        return result.stdout.strip()
    except Exception as e:
        return f"Unexpected error: {str(e)}"