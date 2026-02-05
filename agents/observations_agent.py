import os
import json
from core.state import AgentState, Observations, Artifacts
from core.llm import get_llm, invoke_llm_with_retry
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from prompts.observation import OBSERVATION_PROMPT

def observation_agent(state: AgentState) -> AgentState:
    """
    Observation Agent: Processes tool outputs into structured observations and artifacts using LLM.
    """
    log = state.get("execution_log", [])
    if not log:
        return state

    last_entry = log[-1]
    if last_entry.get("error"):
        # Handle error in log if necessary
        return state

    # Initialize LLM
    llm = get_llm(temperature=0.1)

    # Prepare inputs for the prompt
    tool_name = last_entry.get("tool")
    tool_input = json.dumps(last_entry.get("input", {}))
    tool_output = last_entry.get("output", "No output")
    
    current_obs = state.get("observations") or {"strings": [], "code": [], "runtime": []}
    
    # Format the prompt
    print(f"[OBSERVATION] Analyzing output from {tool_name}...")
    prompt_template = ChatPromptTemplate.from_template(OBSERVATION_PROMPT)
    chain = prompt_template | llm | JsonOutputParser()

    try:
        response = invoke_llm_with_retry(chain, {
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "current_observations": json.dumps(current_obs)
        })

        # Update Observations
        new_obs = response.get("new_observations", {})
        print(f"[OBSERVATION] Found {len(new_obs.get('strings', []))} new strings, {len(new_obs.get('code', []))} code items.")
        
        if "observations" not in state or state["observations"] is None:
            state["observations"] = Observations(strings=[], code=[], runtime=[])
        
        state["observations"]["strings"].extend(new_obs.get("strings", []))
        state["observations"]["code"].extend(new_obs.get("code", []))
        state["observations"]["runtime"].extend(new_obs.get("runtime", []))

        # Update Artifacts
        new_arts = response.get("new_artifacts", {})
        if new_arts.get("notes"):
            print(f"[OBSERVATION] New notes: {new_arts['notes']}")
        
        if "artifacts" not in state or state["artifacts"] is None:
            state["artifacts"] = Artifacts(
                decoded_strings=[], 
                extracted_keys=[], 
                decrypted_payloads=[], 
                notes=[]
            )
        
        state["artifacts"]["decoded_strings"].extend(new_arts.get("decoded_strings", []))
        state["artifacts"]["extracted_keys"].extend(new_arts.get("extracted_keys", []))
        state["artifacts"]["decrypted_payloads"].extend(new_arts.get("decrypted_payloads", []))
        state["artifacts"]["notes"].extend(new_arts.get("notes", []))

        # Update Target Info if provided
        target_updates = response.get("updated_target_info", {})
        if target_updates:
            print(f"[OBSERVATION] Updating target info: {target_updates}")
            if "target" not in state or state["target"] is None:
                state["target"] = {}
            
            for key in ["binary_type", "arch", "os", "stripped"]:
                if key in target_updates and target_updates[key] is not None:
                    state["target"][key] = target_updates[key]

    except Exception as e:
        print(f"Error in Observation Agent: {e}")
        # Fallback: very simple note
        if "artifacts" not in state or state["artifacts"] is None:
             state["artifacts"] = {"notes": []}
        state["artifacts"]["notes"].append(f"Processed output from {tool_name} (fallback)")

    return state