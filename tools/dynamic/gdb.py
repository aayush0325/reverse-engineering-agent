import subprocess
from typing import List, Optional
from langchain_core.tools import tool

@tool
def gdb_tool(binary_path: str, commands: List[str]) -> str:
    """
    Executes multiple GDB commands on a binary in batch mode and returns the combined output.
    This allows 'interactive' debugging by providing a sequence of commands like break, run, info, etc.
    
    Args:
        binary_path: The absolute path to the binary file.
        commands: A list of GDB commands to execute (e.g., ["break main", "run", "info registers"]).
    
    Returns:
        The output from GDB or an error message.
    """
    try:
        # Build the GDB command
        # --batch: Exit after processing all commands
        # -ex <cmd>: Execute a single command
        gdb_cmd = ["gdb", "--batch", "--quiet"]
        
        for cmd in commands:
            gdb_cmd.extend(["-ex", cmd])
        
        gdb_cmd.append(binary_path)
        
        result = subprocess.run(
            gdb_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30  # Safety timeout for hangs
        )
        
        if result.returncode != 0:
            return f"GDB Error (Exit {result.returncode}):\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired:
        return "Error: GDB execution timed out after 30 seconds."
    except Exception as e:
        return f"Unexpected error running GDB: {str(e)}"