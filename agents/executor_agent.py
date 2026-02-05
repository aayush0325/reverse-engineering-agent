import os
import json
from typing import Any, Dict, List
from core.state import AgentState, ExecutionLogEntry
from core.llm import get_llm, invoke_llm_with_retry
from tools.static import file_tool, hexdump_tool, strings_tool
from tools.dynamic import gdb_tool, run_binary_tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def executor_agent(state: AgentState) -> AgentState:
    """
    Executor Agent: Picks the next pending step from the plan and executes it.
    For complex tools like GDB, it uses an LLM to translate the action into specific commands.
    """
    plan = state.get("current_plan", [])
    next_step = next((step for step in plan if step["status"] == "pending"), None)

    if not next_step:
        return state

    tool_name = next_step.get("tool")
    binary_path = state.get("target", {}).get("binary_path")

    if not binary_path:
        error_msg = "Error: No binary path provided in target info."
        if "execution_log" not in state or state["execution_log"] is None:
            state["execution_log"] = []
        state["execution_log"].append(ExecutionLogEntry(
            step_id=next_step["step_id"],
            tool=tool_name,
            input={},
            output=None,
            error=error_msg
        ))
        next_step["status"] = "failed"
        return state

    # Tool mapping
    tool_map = {
        "file": file_tool,
        "strings": strings_tool,
        "hexdump": hexdump_tool,
        "gdb": gdb_tool,
        "run_binary": run_binary_tool
    }

    output = None
    error = None
    tool_input = {"binary_path": binary_path}

    if tool_name in tool_map:
        try:
            print(f"[EXECUTOR] Executing Step {next_step['step_id']}: {next_step['action']} using {tool_name}")
            tool_func = tool_map[tool_name]
            
            # Use LLM for tools that need complex input translation
            if tool_name in ["gdb", "run_binary"]:
                print(f"[EXECUTOR] Translating action to {tool_name} inputs...")
                llm = get_llm(temperature=0.0)
                
                obs = state.get("observations", {})
                arts = state.get("artifacts", {})
                obs_summary = ""
                if obs.get("strings"):
                    obs_summary += "Strings found: " + ", ".join([s["value"] for s in obs["strings"][:20]])
                if arts.get("notes"):
                    obs_summary += "\nNotes: " + "; ".join(arts["notes"])

                if tool_name == "gdb":
                    prompt_text = """
                    Convert action to GDB commands JSON.
                    Action: {action}
                    Binary: {binary_path}
                    Observations: {observations}
                    Last Tool Output: {last_output}
                    Output: {{"commands": ["cmd1", ...]}}
                    """
                else: # run_binary
                    prompt_text = """
                    Convert action to execution arguments and stdin JSON.
                    IMPORTANT: If 'Last Tool Output' or 'Observations' suggest a prompt (e.g. 'Enter key:'), 
                    provide the expected input in 'stdin_data'.
                    Action: {action}
                    Binary: {binary_path}
                    Observations: {observations}
                    Last Tool Output: {last_output}
                    Output: {{"cmd_args": ["--arg1", "val"], "stdin_data": "input string\\n"}}
                    """
                
                prompt = ChatPromptTemplate.from_template(prompt_text)
                chain = prompt | llm | JsonOutputParser()
                
                last_log = state["execution_log"][-1] if state.get("execution_log") else {}
                last_output = last_log.get("output", "No previous output")

                translation = invoke_llm_with_retry(chain, {
                    "action": next_step["action"],
                    "binary_path": binary_path,
                    "observations": obs_summary,
                    "last_output": last_output
                })
                
                if tool_name == "gdb":
                    tool_input["commands"] = translation.get("commands", ["break main", "run", "quit"])
                    print(f"[EXECUTOR] GDB Commands: {tool_input['commands']}")
                else:
                    tool_input["cmd_args"] = translation.get("cmd_args", [])
                    tool_input["stdin_data"] = translation.get("stdin_data")
                    print(f"[EXECUTOR] Args: {tool_input['cmd_args']}, Stdin: {tool_input['stdin_data']}")
                
                result = tool_func.invoke(tool_input)
            else:
                # Static tools just take binary_path
                result = tool_func.invoke(tool_input)
            
            output = str(result)
            print(f"[EXECUTOR] Tool output received ({len(output)} chars)")
        except Exception as e:
            error = f"Tool execution failed: {str(e)}"
    else:
        error = f"Unsupported tool: {tool_name}"

    # Log the execution
    log_entry = ExecutionLogEntry(
        step_id=next_step["step_id"],
        tool=tool_name,
        input=tool_input,
        output=output,
        error=error
    )
    
    if "execution_log" not in state or state["execution_log"] is None:
        state["execution_log"] = []
    
    state["execution_log"].append(log_entry)
    
    # Update step status
    if error:
        next_step["status"] = "failed"
    else:
        next_step["status"] = "completed"
    
    next_step["result_ref"] = f"log_{len(state['execution_log'])-1}"

    return state