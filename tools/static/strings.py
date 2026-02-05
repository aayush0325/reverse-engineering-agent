import subprocess
from langchain_core.tools import tool

@tool
def strings_tool(binary_path: str, min_len: int = 4) -> str:
    """
    Extracts printable strings from a binary file.
    
    Args:
        binary_path: The absolute path to the binary file.
        min_len: The minimum length of strings to extract (default 4).
    
    Returns:
        A list of strings found in the binary, or an error message.
    """
    try:
        # Run strings -n <min_len> <path>
        result = subprocess.run(
            ["strings", "-n", str(min_len), binary_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
        
        # Limit output if it's too large
        lines = result.stdout.strip().splitlines()
        if len(lines) > 500:
            return "\n".join(lines[:500]) + "\n... (truncated)"
        
        return result.stdout.strip()
    except Exception as e:
        return f"Unexpected error: {str(e)}"