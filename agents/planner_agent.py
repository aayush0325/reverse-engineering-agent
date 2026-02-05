import os
import json
from typing import List
from core.state import AgentState, PlanStep, Hypothesis
from core.llm import get_llm, invoke_llm_with_retry
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from prompts.planner import PLANNER_PROMPT

def planner_agent(state: AgentState) -> AgentState:
    """
    Planner Agent: Analyzes the target and goal to generate hypotheses and a plan using LLM.
    """
    # Only plan if no plan exists or we are re-planning
    if state.get("current_plan") and any(s["status"] != "completed" for s in state["current_plan"]):
        # If there's already an active plan, we might not want to overwrite it 
        # unless specifically triggered. For now, let's keep it simple.
        return state

    # Initialize LLM
    llm = get_llm(temperature=0.1)

    # Prepare inputs for the prompt
    target = state.get("target", {})
    goal = state.get("goal", {})
    obs = state.get("observations", {})
    arts = state.get("artifacts", {})
    
    # Check what we already know to avoid redundancy
    known_info = []
    if target.get("binary_type") and target.get("binary_type") != "Unknown":
        known_info.append(f"Binary Type: {target['binary_type']}")
    if target.get("arch") and target.get("arch") != "Unknown":
        known_info.append(f"Arch: {target['arch']}")
    if target.get("stripped") is not None:
        known_info.append("Stripped: " + str(target["stripped"]))
    
    existing_observations = ""
    if obs.get("strings"):
        existing_observations += f"\nStrings already found: " + ", ".join([s["value"] for s in obs["strings"][:15]])
    if arts.get("notes"):
        existing_observations += f"\nKey Notes: " + "; ".join(arts["notes"])

    system_info = f"Path: {target.get('binary_path')}\n" + "\n".join(known_info) + existing_observations
    goal_str = f"Objective: {goal.get('primary_objective')}"
    
    constraints = "Skip basic information gathering (file/strings) if the information is already clearly present in the observations. Focus on testing leads and deep analysis."

    print(f"\n[PLANNER] Analyzing target and generating plan...")
    
    # Format the prompt
	
    prompt_template = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = prompt_template | llm | JsonOutputParser()

    try:
        response = invoke_llm_with_retry(chain, {
            "system_info": system_info,
            "goal": goal_str,
            "constraints": constraints
        })

        # Map response to AgentState
        llm_plan = response.get("plan", [])
        print(f"[PLANNER] Generated {len(llm_plan)} steps.")
        new_plan: List[PlanStep] = []
        
        for i, step in enumerate(llm_plan):
            tool = step.get("tool", "unknown").lower()
            # Canonicalize tool name
            if "strings" in tool: tool = "strings"
            elif "file" in tool: tool = "file"
            elif "hexdump" in tool: tool = "hexdump"
            elif "run" in tool: tool = "run_binary"
            elif "gdb" in tool: tool = "gdb"
            
            print(f"  - Step {i+1}: {step.get('title')} ({tool})")

            new_plan.append(PlanStep(
                step_id=step.get("step", i + 1),
                action=step.get("description", step.get("title", "Unknown Action")),
                tool=tool,
                status="pending",
                result_ref=None
            ))

        state["current_plan"] = new_plan

        # Generate initial hypotheses based on the plan/goal
        if not state.get("hypotheses"):
            state["hypotheses"] = [
                Hypothesis(
                    id="h1",
                    claim=f"The goal '{goal.get('primary_objective')}' can be achieved by following the generated plan.",
                    confidence=0.5,
                    evidence=[],
                    status="active"
                )
            ]

    except Exception as e:
        print(f"Error in Planner Agent: {e}")
        # Fallback to a very basic plan if LLM fails
        if not state.get("current_plan"):
            state["current_plan"] = [
                PlanStep(step_id=1, action="Manual inspection", tool="file", status="pending", result_ref=None)
            ]

    return state