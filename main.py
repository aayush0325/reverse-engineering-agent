import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from core.graph import create_graph
from core.state import (
    AgentState, TargetInfo, Goal, Observations, 
    Artifacts, Confidence, Termination
)
from core.llm import set_llm_config

def main():
    parser = argparse.ArgumentParser(description="Reverse Engineering Agent CLI")
    parser.add_argument("--path", required=True, help="Path to the binary file to analyze")
    parser.add_argument("--prompt", required=True, help="The reverse engineering goal or prompt")
    parser.add_argument("--provider", default="groq", choices=["groq", "gemini"], help="LLM provider (default: groq)")
    parser.add_argument("--model", help="Specific model name (optional)")
    
    args = parser.parse_args()
    
    # Configure LLM provider and model
    set_llm_config(args.provider, args.model)
    
    binary_path = os.path.abspath(args.path)
    if not os.path.exists(binary_path):
        print(f"Error: File not found at {binary_path}")
        sys.exit(1)

    if args.provider == "groq" and not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY environment variable is not set. Groq calls will fail.")
    if args.provider == "gemini" and not os.environ.get("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY environment variable is not set. Gemini calls will fail.")

    # Initialize the starting state for the agent
    initial_state: AgentState = {
        "target": TargetInfo(
            binary_path=binary_path,
            binary_type="Unknown",
            arch="Unknown",
            os="Unknown",
            stripped=None,
            protections=[],
            entrypoint=None
        ),
        "goal": Goal(
            primary_objective=args.prompt,
            sub_goals=[]
        ),
        "hypotheses": [],
        "observations": Observations(strings=[], code=[], runtime=[]),
        "artifacts": Artifacts(
            decoded_strings=[], 
            extracted_keys=[], 
            decrypted_payloads=[], 
            notes=[]
        ),
        "current_plan": [],
        "execution_log": [],
        "blockers": [],
        "confidence": Confidence(understanding_level=0.0, unanswered_questions=[]),
        "termination": Termination(satisfied=False, reason=None)
    }

    print(f"[*] Starting analysis for: {binary_path}")
    print(f"[*] Goal: {args.prompt}")
    print("-" * 50)
    
    try:
        # Create and compile the LangGraph
        graph = create_graph()
        
        # Invoke the graph with the initial state
        # In a real CLI, you might want to stream to show progress, 
        # but invoke is the most straightforward for a single-pass run.
        print("[*] Running agentic loop...")
        final_state = graph.invoke(initial_state)
        
        print("\n" + "="*50)
        print("ANALYSIS RESULTS")
        print("="*50)
        
        # Display results
        conf = final_state.get('confidence', {})
        print(f"Confidence Level: {conf.get('understanding_level', 0.0)}")
        
        term = final_state.get('termination', {})
        print(f"Status: {'SUCCESS' if term.get('satisfied') else 'PROGRESSING/STOPPED'}")
        print(f"Reason: {term.get('reason', 'N/A')}")
        
        if final_state.get('artifacts', {}).get('notes'):
            print("\nKey Findings/Notes:")
            for note in final_state['artifacts']['notes']:
                print(f" - {note}")
        
        if final_state.get('hypotheses'):
            print("\nHypotheses:")
            for h in final_state['hypotheses']:
                print(f" - [{h.get('status', '??').upper()}] {h.get('claim')} (Conf: {h.get('confidence')})")

        if final_state.get('observations', {}).get('strings'):
            print(f"\nTotal Strings Observed: {len(final_state['observations']['strings'])}")

    except Exception as e:
        print(f"\n[!] Error during agent execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
