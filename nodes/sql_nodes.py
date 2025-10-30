"""
Simple SQL Agent Nodes for LangGraph
Handles user input, SQL query execution, and response generation
"""

from langchain_ollama import OllamaLLM
from .state_schemas import TimeManagementState
from datetime import datetime
import json
import os


# Initialize LLM (local Ollama) - fallback to mock if not available
def get_llm():
    """Get LLM instance, with fallback to mock"""
    try:
        return OllamaLLM(model="gpt-oss:20b-cloud", temperature=0.1)
    except:
        # Fallback to mock LLM for testing
        class MockLLM:
            def invoke(self, prompt: str) -> str:
                # Simple mock responses
                if "CREATE TABLE" in prompt.upper():
                    return json.dumps({
                        "intent": "create",
                        "sql_query": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)",
                        "explanation": "Creating users table"
                    })
                elif "INSERT" in prompt.upper():
                    return json.dumps({
                        "intent": "insert",
                        "sql_query": "INSERT INTO users (name, email) VALUES ('John Doe', 'john@example.com')",
                        "explanation": "Inserting test user"
                    })
                elif "SELECT" in prompt.upper() or "SHOW" in prompt.upper():
                    return json.dumps({
                        "intent": "select",
                        "sql_query": "SELECT * FROM sqlite_master WHERE type='table'",
                        "explanation": "Showing all tables"
                    })
                else:
                    return json.dumps({
                        "intent": "select",
                        "sql_query": "SELECT 1",
                        "explanation": "Default query"
                    })
        return MockLLM()

llm = get_llm()


def user_input_node(state: TimeManagementState) -> TimeManagementState:
    """
    Node 1: Receives and processes user input.
    Just stores the current input in state.
    """
    # In a real Chainlit scenario, this would come from user message
    # For now, we ensure current_input is set
    
    action = "user_input_received"
    state["action_taken"] = action
    state["last_sync_with_db"] = datetime.now().isoformat()
    
    print(f"📝 User Input: {state.get('current_input', 'No input')}")
    
    return state


def classify_intent_node(state: TimeManagementState) -> TimeManagementState:
    """
    Node 2: Classify user intent and generate SQL query.
    Returns decision on which SQL operation to perform.
    """
    user_input = state.get("current_input", "")
    
    prompt = f"""You are a SQL query assistant. Analyze this user request and generate appropriate SQL.

User Request: "{user_input}"

Respond in this JSON format only:
{{
    "intent": "select|insert|update|delete|create",
    "sql_query": "THE EXACT SQL QUERY",
    "explanation": "Brief explanation of what you're doing"
}}

IMPORTANT: 
- Only generate valid SQL queries
- If uncertain, use SELECT to view existing data
- Always return valid JSON
"""
    
    response = llm.invoke(prompt)
    
    print(f"🧠 LLM Response:\n{response}\n")
    
    try:
        parsed = json.loads(response)
        state["reasoning"] = parsed.get("explanation", "")
        state["next_step"] = "execute_sql"
        state["action_taken"] = "classified_intent"
        state["sql_query"] = parsed.get("sql_query", "")
        state["intent"] = parsed.get("intent", "select")
        
        return state
        
    except json.JSONDecodeError:
        print(f"❌ Failed to parse LLM response")
        state["action_taken"] = "failed_to_parse_intent"
        state["next_step"] = "handle_error"
        state["sql_query"] = ""
        state["intent"] = "error"
        
        return state


def execute_sql_node(state: TimeManagementState) -> TimeManagementState:
    """
    Node 3: Execute the SQL query via MCP tools.
    This node will be called by Chainlit with actual MCP session.
    """
    sql_query = state.get("sql_query", "")
    
    if not sql_query:
        state["action_taken"] = "no_sql_query"
        state["reasoning"] = "No valid SQL query was generated"
        return state
    
    print(f"💾 Executing SQL: {sql_query}")
    
    # Placeholder: In real integration with Chainlit, 
    # MCP session will execute this via query_data tool
    state["action_taken"] = "sql_executed"
    state["is_db_updated"] = True
    state["last_sync_with_db"] = datetime.now().isoformat()
    
    # This will store result from MCP call
    # For now, simulate a successful execution
    state["sql_result"] = f"✅ SQL executed: {sql_query[:50]}..."
    
    return state


def generate_response_node(state: TimeManagementState) -> TimeManagementState:
    """
    Node 4: Generate user-friendly response from SQL result.
    """
    sql_result = state.get("sql_result", "No result")
    user_input = state.get("current_input", "")
    
    prompt = f"""Based on this SQL result, provide a friendly response to the user's request.

User Asked: "{user_input}"
SQL Result: {sql_result}

Provide a concise, user-friendly response:
"""
    
    response = llm.invoke(prompt)
    
    print(f"✅ Generated Response:\n{response}\n")
    
    # Add to conversation history
    messages = state.get("messages", [])
    messages.append({
        "role": "user",
        "content": user_input
    })
    messages.append({
        "role": "assistant",
        "content": response
    })
    
    state["messages"] = messages
    state["action_taken"] = "response_generated"
    
    return state
