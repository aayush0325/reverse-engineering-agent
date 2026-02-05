from langgraph.prebuilt import ToolNode
from tools.static import file_tool, hexdump_tool, strings_tool
from tools.dynamic import gdb_tool, run_binary_tool

tools = [file_tool, hexdump_tool, strings_tool, gdb_tool, run_binary_tool]

tool_node = ToolNode(tools)