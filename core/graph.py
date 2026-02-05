from typing import Literal
from langgraph.graph import StateGraph, START, END
from core.state import AgentState
from agents import planner_agent, critic_agent, executor_agent, observation_agent

def create_graph():
	graph = StateGraph(AgentState)

	graph.add_node('planning', planner_agent)
	graph.add_node('executor', executor_agent)
	graph.add_node('observation', observation_agent)
	graph.add_node('critic', critic_agent)

	graph.add_edge(START, 'planning')
	graph.add_edge('planning', 'executor')
	graph.add_edge('executor', 'observation')
	graph.add_edge('observation', 'critic')

	def should_continue(state: AgentState) -> Literal['executor', END]:
		if state['termination']['satisfied']:
			return END
		return 'executor'

	graph.add_conditional_edges(
		'critic',
		should_continue,
		{
			'executor': 'executor',
			END: END
		}
	)

	return graph.compile()