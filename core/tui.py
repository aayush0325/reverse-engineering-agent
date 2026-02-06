import asyncio
import re
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult

# Pattern to match ANSI escape codes
ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[PX^_][^\x1b]*\x1b\\')

def sanitize_output(text: str) -> str:
    """Strip ANSI escape codes and control characters from text for clean TUI display."""
    if not text:
        return ""
    # Remove ANSI escape sequences
    text = ANSI_ESCAPE_PATTERN.sub('', text)
    # Remove other control characters except newlines and tabs
    text = ''.join(c if c == '\n' or c == '\t' or (ord(c) >= 32 and ord(c) < 127) or ord(c) >= 160 else ' ' for c in text)
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()

from textual.containers import Container, Horizontal, Vertical, ScrollableContainer, VerticalScroll
from textual.widgets import Header, Footer, Static, DataTable, RichLog, TabbedContent, TabPane, ProgressBar, Label, LoadingIndicator
from textual.reactive import reactive
from textual.worker import Worker, WorkerState

from core.graph import create_graph
from core.state import AgentState

class Sidebar(Vertical):
    """A sidebar to show global agent status."""
    
    def compose(self) -> ComposeResult:
        yield Label("[b]TARGET INFO[/b]", classes="section-title")
        yield Static("Path: N/A", id="target-path")
        yield Static("Type: Unknown", id="target-type")
        yield Static("Arch: Unknown", id="target-arch")
        
        yield Label("\n[b]CONFIDENCE[/b]", classes="section-title")
        yield ProgressBar(total=100, show_bar=True, show_percentage=True, id="conf-bar")
        
        yield Label("\n[b]GOAL[/b]", classes="section-title")
        yield Static("Initializing...", id="goal-text", classes="goal-box")
        
        yield Label("\n[b]STATUS[/b]", classes="section-title")
        yield Static("Idle", id="status-text")
        yield LoadingIndicator(id="loading-indicator")

class PlanStepWidget(Horizontal):
    """A widget for an individual plan step."""
    def __init__(self, step: Dict[str, Any]):
        self.step = step
        super().__init__(classes="plan-step")

    def compose(self) -> ComposeResult:
        step_id = self.step.get("step_id", "?")
        tool = self.step.get("tool", "unknown")
        action = self.step.get("action", "")
        status = self.step.get("status", "pending")
        
        status_style = "green" if status == "completed" else "yellow" if status == "pending" else "red"
        
        yield Label(f"[b]{step_id}. [{tool}][/b]", classes="step-meta")
        yield Label(action, classes="step-action")
        yield Label(f"[{status_style}]{status}[/]", classes="step-status")

class ToolCallWidget(Vertical):
    """A widget for a structured tool call entry with scrollable output."""
    def __init__(self, entry: Dict[str, Any]):
        self.entry = entry
        super().__init__(classes="tool-call-item")

    def compose(self) -> ComposeResult:
        tool = self.entry.get("tool", "unknown")
        inputs = self.entry.get("input", {})
        output = self.entry.get("output", "")
        error = self.entry.get("error")
        
        yield Label(f"[bold magenta]Tool:[/] [b]{tool}[/b]", classes="tool-header")
        
        # Input section
        with Vertical(classes="tool-section"):
            yield Label("[dim]Input:[/]", classes="section-label")
            with Vertical(classes="tool-input-content"):
                if isinstance(inputs, dict):
                    for k, v in inputs.items():
                        # Sanitize and handle long values
                        val_str = sanitize_output(str(v))
                        yield Static(f"[cyan]{k}[/]: {val_str}", classes="input-line")
                else:
                    yield Static(sanitize_output(str(inputs)), classes="input-line")
        
        # Output section with scrollable container for long outputs
        if output:
            # Sanitize output to remove ANSI codes from tools like gdb
            clean_output = sanitize_output(str(output))
            with Vertical(classes="tool-section"):
                yield Label("[dim]Output:[/]", classes="section-label")
                with ScrollableContainer(classes="tool-output-scroll"):
                    yield Static(clean_output, classes="tool-output")
                
        # Error section
        if error:
            clean_error = sanitize_output(str(error))
            with Vertical(classes="tool-section tool-error-section"):
                yield Static(f"[bold red]Error:[/] {clean_error}", classes="tool-error")

class AgentApp(App):
    """Textual TUI for the Reverse Engineering Agent."""
    
    CSS = """
    Screen {
        background: #1e1e2e;
        color: #cdd6f4;
    }
    
    Sidebar {
        width: 40;
        background: #181825;
        padding: 1;
        border-right: tall #313244;
    }
    
    Sidebar Static {
        width: 100%;
        content-align: left middle;
    }
    
    .section-title {
        color: #f5e0dc;
        margin-bottom: 1;
        text-style: bold;
    }
    
    .goal-box {
        background: #313244;
        padding: 1;
        border: round #45475a;
    }
    
    TabbedContent {
        height: 1fr;
    }
    
    DataTable {
        height: 1fr;
        border: round #313244;
    }
    
    RichLog {
        height: 1fr;
        border: round #313244;
    }
    
    #main-container {
        padding: 1;
    }
    
    #status-text {
        color: #fab387;
        margin-bottom: 1;
    }
    
    #loading-indicator {
        height: 3;
        color: #89b4fa;
    }

    .plan-step {
        height: auto;
        min-height: 3;
        background: #1e1e2e;
        border: round #313244;
        margin-bottom: 1;
        padding: 1;
    }
    .step-meta {
        width: 15;
    }
    .step-action {
        width: 1fr;
        text-wrap: wrap;
    }
    .step-status {
        width: 15;
        content-align: right middle;
    }

    .tool-call-item {
        background: #181825;
        border: round #313244;
        margin-bottom: 2;
        padding: 1;
        height: auto;
        width: 100%;
    }
    .tool-header {
        color: #cba6f7;
        margin-bottom: 1;
        text-style: bold;
    }
    .tool-section {
        padding-left: 1;
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    .section-label {
        color: #6c7086;
        margin-bottom: 0;
    }
    .tool-input-content {
        padding-left: 1;
        width: 100%;
        height: auto;
    }
    .input-line {
        text-wrap: wrap;
        width: 100%;
        color: #cdd6f4;
    }
    .tool-output-scroll {
        max-height: 20;
        height: auto;
        width: 100%;
        border: round #45475a;
        background: #1e1e2e;
        padding: 1;
    }
    .tool-output {
        color: #a6e3a1;
        text-wrap: wrap;
        width: 100%;
    }
    .tool-error-section {
        background: #302030;
        padding: 1;
        border: round #f38ba8;
    }
    .tool-error {
        color: #f38ba8;
        text-wrap: wrap;
        width: 100%;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "app.toggle_dark", "Toggle Dark Mode"),
    ]
    
    def __init__(self, initial_state: AgentState):
        super().__init__()
        self.agent_state = initial_state
        self.graph = create_graph()
        self.current_worker: Optional[Worker] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar()
            with Vertical(id="main-container"):
                with TabbedContent(initial="plan"):
                    with TabPane("Plan", id="plan"):
                        yield VerticalScroll(id="plan-list")
                    with TabPane("Observations", id="obs"):
                        yield DataTable(id="obs-table")
                    with TabPane("Tool Calls", id="tool-calls"):
                        yield VerticalScroll(id="tool-calls-list")
                    with TabPane("Findings", id="findings"):
                        yield RichLog(id="findings-log", markup=True, wrap=True)
                    with TabPane("Critic", id="critic-tab"):
                        yield RichLog(id="critic-log", markup=True, wrap=True)
                    with TabPane("Full Log", id="full-log"):
                        yield RichLog(id="execution-log", markup=True, wrap=True)
                    with TabPane("Summary", id="summary"):
                        yield RichLog(id="summary-view", markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets and start the agent."""
        self.title = "Reverse Engineering Agent"
        self.sub_title = "Building a deeper understanding..."
        
        # Setup Tables
        obs_table = self.query_one("#obs-table", DataTable)
        obs_table.add_columns("Category", "Observation")
        
        # Set initial values
        self.update_sidebar(self.agent_state)
        
        # Start logical worker
        self.run_agent()

    def update_sidebar(self, state: AgentState) -> None:
        target = state.get("target", {})
        self.query_one("#target-path", Static).update(f"Path: {target.get('binary_path', 'N/A')}")
        self.query_one("#target-type", Static).update(f"Type: {target.get('binary_type', 'Unknown')}")
        self.query_one("#target-arch", Static).update(f"Arch: {target.get('arch', 'Unknown')}")
        
        goal = state.get("goal", {})
        self.query_one("#goal-text", Static).update(goal.get("primary_objective", "No Goal"))
        
        conf = state.get("confidence", {})
        level = conf.get("understanding_level", 0.0) * 100
        self.query_one("#conf-bar", ProgressBar).progress = level

    def update_ui_from_state(self, state: AgentState) -> None:
        self.agent_state = state
        self.update_sidebar(state)
        
        # Update Plan List
        plan_list = self.query_one("#plan-list", VerticalScroll)
        # Clear existing steps correctly in Textual
        plan_list.remove_children()
        for step in state.get("current_plan", []):
            plan_list.mount(PlanStepWidget(step))
            
        # Update Observations
        obs_table = self.query_one("#obs-table", DataTable)
        obs_table.clear()
        obs = state.get("observations", {})
        def safe_hex(val):
            try:
                if isinstance(val, str):
                    if val.startswith("0x"): return val
                    return hex(int(val))
                return hex(val)
            except:
                return str(val)

        for s in obs.get("strings", []):
            obs_table.add_row("String", f"{s.get('value')} (at {safe_hex(s.get('offset', 0))})")
        for c in obs.get("code", []):
            obs_table.add_row("Code", f"Func at {safe_hex(c.get('function_addr', 0))}: {c.get('summary')}")
            
        # Update Findings Log
        findings_log = self.query_one("#findings-log", RichLog)
        findings_log.clear()
        arts = state.get("artifacts", {})
        for note in arts.get("notes", []):
            findings_log.write(f"• {note}\n")

        # Update Tool Calls List
        tool_list = self.query_one("#tool-calls-list", VerticalScroll)
        tool_list.remove_children()
        for entry in state.get("execution_log", []):
            tool_list.mount(ToolCallWidget(entry))

        # Update Summary View if finished
        term = state.get("termination", {})
        if term.get("satisfied") or any(s["status"] == "completed" for s in state.get("current_plan", [])):
            summary_view = self.query_one("#summary-view", RichLog)
            summary_view.clear()
            summary_view.write("[bold cyan]=== ANALYSIS SUMMARY ===[/]\n\n")
            target = state.get("target", {})
            summary_view.write(f"[b]Target:[/] {target.get('binary_path')}\n")
            summary_view.write(f"Type: {target.get('binary_type')} | Arch: {target.get('arch')}\n\n")
            
            summary_view.write(f"[b]Status:[/] {'[green]SUCCESS[/]' if term.get('satisfied') else '[yellow]IN PROGRESS[/]'}\n")
            summary_view.write(f"[b]Reason:[/] {term.get('reason', 'N/A')}\n\n")
            
            for note in arts.get("notes", []):
                summary_view.write(f"  • {note}\n")

        # Update Critic Log
        critic_log = self.query_one("#critic-log", RichLog)
        critic_log.clear()
        conf = state.get("confidence", {})
        term = state.get("termination", {})
        
        critic_log.write("[bold cyan]=== CRITICAL EVALUATION ===[/]\n\n")
        level = conf.get("understanding_level", 0.0) * 100
        critic_log.write(f"[b]Confidence Level:[/] [yellow]{level:.1f}%[/]\n")
        critic_log.write(f"[b]Goal Satisfied:[/] {'[green]Yes[/]' if term.get('satisfied') else '[red]No[/]'}\n\n")
        
        if term.get("reason"):
            critic_log.write(f"[b]Analysis Reasoning:[/]\n{term.get('reason')}\n\n")
            
        if conf.get("unanswered_questions"):
            critic_log.write("[bold red]Unanswered Questions:[/]\n")
            for q in conf["unanswered_questions"]:
                critic_log.write(f"  ? {q}\n")

    def run_agent(self) -> None:
        """Runs the LangGraph agent in a background worker."""
        self.current_worker = self.run_worker(self._run_agent_task(), exclusive=True)

    async def _run_agent_task(self) -> None:
        log = self.query_one("#execution-log", RichLog)
        status = self.query_one("#status-text", Static)
        loader = self.query_one("#loading-indicator", LoadingIndicator)
        
        log.write("[bold blue][*] Starting Agentic Loop...[/]\n")
        
        try:
            # Show loader initially
            loader.display = True
            
            # We use stream to get intermediate updates
            async for output in self.graph.astream(self.agent_state):
                # Update status based on what's coming next (simplified)
                status.update("Thinking...")
                
                for node_name, state_update in output.items():
                    log.write(f"[bold green][+][/] Completed node: [cyan]{node_name}[/]\n")
                    
                    # Update status message
                    if node_name == "planning":
                        status.update("Step Execution...")
                    elif node_name == "executor":
                        status.update("Analyzing Results...")
                    elif node_name == "observation":
                        status.update("Critiquing Plan...")
                    elif node_name == "critic":
                        if state_update.get("termination", {}).get("satisfied"):
                            status.update("Complete!")
                            loader.display = False
                        else:
                            status.update("Refining Plan...")
                    
                    # Auto-navigation logic
                    tabbed_content = self.query_one(TabbedContent)
                    if node_name == "planning":
                        tabbed_content.active = "plan"
                    elif node_name == "executor":
                        tabbed_content.active = "tool-calls"
                    elif node_name == "observation":
                        tabbed_content.active = "obs"
                    elif node_name == "critic":
                        # If satisfied, go to summary, else show critic tab
                        if state_update.get("termination", {}).get("satisfied"):
                            tabbed_content.active = "summary"
                        else:
                            tabbed_content.active = "critic-tab"

                    # Update local state
                    self.agent_state.update(state_update)
                    self.update_ui_from_state(self.agent_state)
            
            log.write("\n[bold green][SUCCESS] Analysis Complete![/]\n")
            term = self.agent_state.get("termination", {})
            log.write(f"Reason: {term.get('reason', 'N/A')}\n")
            status.update("Complete!")
            loader.display = False
            
            # Final navigation to summary
            if term.get("satisfied"):
                self.query_one(TabbedContent).active = "summary"
            
        except Exception as e:
            log.write(f"[bold red][!] Error:[/][red] {str(e)}[/]\n")
            status.update("Error!")
            loader.display = False
            import traceback
            log.write(traceback.format_exc())

    def action_toggle_dark(self) -> None:
        # Textual handles toggle_dark automatically if bound to app.toggle_dark
        pass
