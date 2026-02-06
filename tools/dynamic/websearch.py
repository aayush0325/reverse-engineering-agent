import os
from tavily import TavilyClient
from langchain_core.tools import tool

@tool
def web_search_tool(query: str) -> str:
    """
    Performs a web search using the Tavily API to find information online.
    Use this tool when you need to look up documentation, CVEs, or other external information.
    
    Args:
        query: The search query string.
    
    Returns:
        A summarized search result or an error message.
    """
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Error: TAVILY_API_KEY environment variable not set."
        
        client = TavilyClient(api_key=api_key)
        # Search for the query and get a summary
        response = client.search(query=query, search_depth="advanced")
        
        results = []
        for result in response.get("results", []):
            results.append(f"Title: {result.get('title')}\nURL: {result.get('url')}\nContent: {result.get('content')}\n")
        
        if not results:
            return "No results found for the query."
            
        return "\n---\n".join(results)
        
    except Exception as e:
        return f"Error performing web search: {str(e)}"
