import subprocess
import os
import pexpect
import shlex
from typing import List, Optional
from langchain_core.tools import tool

@tool
def run_binary_tool(binary_path: str, cmd_args: List[str] = [], stdin_data: Optional[str] = None) -> str:
    """
    Runs a binary with the specified command-line arguments and optional stdin data.
    Uses pexpect for terminal-like execution, allowing better handling of interactive prompts.
    
    Args:
        binary_path: The absolute path to the binary file.
        cmd_args: A list of command-line arguments to pass to the binary.
        stdin_data: Optional string to send to the binary's stdin. The tool handles multi-line inputs and ensures newline discipline.
    
    Returns:
        A report containing the return code, stdout (including signs of prompts), and stderr.
    """
    try:
        # 1. Path Safety Check
        if not os.path.isabs(binary_path):
             return f"Error: binary_path must be an absolute path: {binary_path}"
        
        if not os.path.isfile(binary_path) or not os.access(binary_path, os.X_OK):
             return f"Error: {binary_path} is not an executable file."

        # 2. Stdin Newline Discipline & Capping
        if stdin_data:
            if len(stdin_data) > 4096:
                 return "Error: stdin_data too large (max 4096 bytes)."
            
            # Ensure it ends with a newline to avoid hangs in fgets()
            if not stdin_data.endswith("\n"):
                stdin_data += "\n"

        # Build command string (pexpect needs a command string or list, but string handles arguments better for some cases)
        cmd_str = f"{binary_path} {' '.join([shlex.quote(str(a)) for a in cmd_args])}"
        
        # 3. Execution using pexpect
        # We spawn the process in a TTY for more realistic behavior
        child = pexpect.spawn(cmd_str, encoding='utf-8', timeout=10)
        
        output = ""
        if stdin_data:
            # We send the data. pexpect will handle the terminal interaction.
            # Multi-line inputs are sent as a block, or we could send line by line.
            # For now, sending the block is most robust for fgets-style binaries.
            child.send(stdin_data)
        
        # Capture all remaining output until the process exits
        try:
            child.expect(pexpect.EOF)
            output = child.before
        except pexpect.TIMEOUT:
            # If we timeout, we capture what we have so far
            output = child.before or ""
            child.terminate(force=True)
            return f"Error: Binary execution timed out after 10 seconds. Output so far:\n\n{output}\n\nThis often happens if the binary is waiting for input that wasn't provided or is an interactive menu."
        
        # Pexpect doesn't give us return code directly easily without wait()
        child.close()
        exit_code = child.exitstatus if child.exitstatus is not None else "Unknown (likely success or EOF)"
        
        report = [
            f"Exit Code: {exit_code}",
            f"Terminal Output (including prompts & responses):\n{output.strip()}"
        ]
        
        return "\n\n".join(report)
        
    except Exception as e:
        return f"Unexpected error running binary with pexpect: {str(e)}"