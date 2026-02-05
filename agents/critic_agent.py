import os
import json
from typing import List
from core.state import AgentState, Confidence, Termination, PlanStep
from core.llm import get_llm, invoke_llm_with_retry
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from prompts.critic import CRITIC_PROMPT

def critic_agent(state: AgentState) -> AgentState:
    """
    Critic / Re-Planner Agent: Evaluates confidence and decides if the goal is met or if re-planning is needed.
    """
    # Initialize LLM
    llm = get_llm(temperature=0.1)

    # Prepare inputs for the prompt
    target = state.get("target", {})
    goal = state.get("goal", {})
    plan = state.get("current_plan", [])
    logs = state.get("execution_log", [])
    obs = state.get("observations", {})
    conf = state.get("confidence", {"understanding_level": 0.0, "unanswered_questions": []})

    target_info = f"Path: {target.get('binary_path')}\nType: {target.get('binary_type')}\nArch: {target.get('arch')}\nStripped: {target.get('stripped')}"
    goal_str = f"Objective: {goal.get('primary_objective')}"
    
    plan_status = "\n".join([f"Step {s['step_id']}: {s['action']} ({s['status']})" for s in plan])
    
    # Summarize observations and artifacts for the LLM
    obs_summary = ""
    if obs:
        if obs.get("strings"):
            obs_summary += "Strings found (" + str(len(obs["strings"])) + "): " + ", ".join([s["value"] for s in obs["strings"][:20]])
        if obs.get("code"):
            obs_summary += "\nFunctions found: " + str(len(obs["code"]))
    
    arts = state.get("artifacts", {})
    if arts.get("notes"):
        obs_summary += "\nKey Findings/Notes: " + "; ".join(arts["notes"])
    
    if not obs_summary:
        obs_summary = "No meaningful observations yet."

    # Format the prompt
    print(f"[CRITIC] Evaluating progress towards goal...")
    prompt_template = ChatPromptTemplate.from_template(CRITIC_PROMPT)
    chain = prompt_template | llm | JsonOutputParser()

    try:
        response = invoke_llm_with_retry(chain, {
            "target_info": target_info,
            "goal": goal_str,
            "plan_status": plan_status,
            "observations": obs_summary,
            "confidence": f"Level: {conf.get('understanding_level')}, Gaps: {', '.join(conf.get('unanswered_questions', []))}"
        })

        # Update confidence
        conf_update = response.get("confidence_update", {})
        state["confidence"] = Confidence(
            understanding_level=conf_update.get("understanding_level", conf.get("understanding_level", 0.0)),
            unanswered_questions=conf_update.get("unanswered_questions", [])
        )
        print(f"[CRITIC] New Confidence Level: {state['confidence']['understanding_level']}")

        # Update termination status
        term = response.get("termination", {})
        state["termination"] = Termination(
            satisfied=term.get("satisfied", False),
            reason=term.get("reason", "No reason provided")
        )
        print(f"[CRITIC] Termination Satisfied: {state['termination']['satisfied']}")
        print(f"[CRITIC] Reason: {state['termination']['reason']}")

        # Handle re-planning if not satisfied
        if not state["termination"]["satisfied"]:
            new_steps_data = response.get("new_steps", [])
            if new_steps_data:
                print(f"[CRITIC] Adding {len(new_steps_data)} new steps to plan.")
                # Add new steps to the plan
                current_max_id = max([s["step_id"] for s in plan]) if plan else 0
                for i, step_data in enumerate(new_steps_data):
                    state["current_plan"].append(PlanStep(
                        step_id=current_max_id + i + 1,
                        action=step_data.get("action", "Unknown action"),
                        tool=step_data.get("tool", "unknown"),
                        status="pending",
                        result_ref=None
                    ))

    except Exception as e:
        print(f"Error in Critic Agent: {e}")
        # Default fallback logic if LLM fails
        plan = state.get("current_plan", [])
        all_done = all(step["status"] == "completed" for step in plan)
        if all_done and plan:
            state["termination"] = Termination(satisfied=True, reason="All planned steps completed (fallback).")
        else:
            state["termination"] = Termination(satisfied=False, reason="Plan still in progress (fallback).")

    return state