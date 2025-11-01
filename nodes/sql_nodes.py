"""
Simplified SQL Agent Nodes for Chainlit
Clean, minimal SQL query generation and execution
"""

from langchain_ollama import OllamaLLM
from .state_schemas import TimeManagementState
from datetime import datetime
import json


# Initialize LLM (local Ollama)
llm = OllamaLLM(model="gpt-oss:20b-cloud", temperature=0.1)


def generate_sql_query(user_input: str, profile_context: dict) -> str:
    """
    Simple function: user input + profile → SQL query
    """
    goals = profile_context.get('goals', 'Not specified')
    strengths = profile_context.get('strengths', 'Not specified')
    
    prompt = f"""You are a SQL expert. Generate a SQL query for this request.

User Goals: {goals}
User Request: "{user_input}"

Respond with ONLY the SQL query, nothing else. Example: SELECT * FROM users;
"""
    
    response = llm.invoke(prompt).strip()
    
    # Clean up response - remove markdown formatting if present
    if response.startswith("```"):
        response = response.split("```")[1]
        if response.startswith("sql"):
            response = response[3:]
    
    return response.strip()


def parse_llm_response_for_tools(response_text: str) -> dict:
    """
    Parse LLM response to extract tool calls
    Returns: {"tool_name": str, "args": dict} or None
    """
    # Look for tool call patterns in LLM response
    if "list_databases" in response_text:
        return {"tool": "list_databases", "args": {}}
    elif "switch_database" in response_text:
        # Extract db name from response
        import re
        match = re.search(r"switch_database\((['\"]?)(\w+)\1\)", response_text)
        if match:
            return {"tool": "switch_database", "args": {"db_name": match.group(2)}}
    elif "query_data" in response_text:
        # Extract SQL from response
        import re
        match = re.search(r"query_data\((['\"])(.*?)\1\)", response_text, re.DOTALL)
        if match:
            return {"tool": "query_data", "args": {"sql": match.group(2)}}
    
    return None


# Legacy workflow nodes (kept for compatibility, now simplified)

def user_profile_node(state: TimeManagementState) -> TimeManagementState:
    """Pass-through: Profile is collected by Chainlit UI"""
    state["action_taken"] = "user_profile_handled"
    return state


def user_input_node(state: TimeManagementState) -> TimeManagementState:
    """Pass-through: Input is from Chainlit"""
    state["action_taken"] = "user_input_received"
    state["last_sync_with_db"] = datetime.now().isoformat()
    return state


def classify_intent_node(state: TimeManagementState) -> TimeManagementState:
    """Generate SQL query from user input"""
    user_input = state.get("current_input", "")
    profile = state.get("personal_characteristics", {})
    
    sql_query = generate_sql_query(user_input, profile)
    
    print(f"📝 Generated SQL: {sql_query}")
    
    return {
        **state,
        "sql_query": sql_query,
        "action_taken": "sql_generated",
        "intent": "select",
    }


def execute_sql_node(state: TimeManagementState) -> TimeManagementState:
    """Placeholder - Chainlit handles MCP execution"""
    state["action_taken"] = "sql_queued_for_execution"
    return state


def generate_response_node(state: TimeManagementState) -> TimeManagementState:
    """Format the SQL result for user"""
    sql_result = state.get("sql_result", "No results")
    messages = state.get("messages", [])
    
    messages.append({
        "role": "assistant",
        "content": f"Result:\n{sql_result}"
    })
    
    state["messages"] = messages
    state["action_taken"] = "response_generated"
    
    return state
