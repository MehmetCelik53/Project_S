"""
Simple SQL Agent Nodes for LangGraph
Handles user input, SQL query execution, and response generation
"""

from langchain_ollama import OllamaLLM
from .state_schemas import TimeManagementState, Goal, Plan
from datetime import datetime
import json
import os
from langgraph.types import interrupt, Command


# Initialize LLM (local Ollama)
llm = OllamaLLM(model="gpt-oss:20b-cloud", temperature=0.1)

# System prompt defining user profile structure
SYSTEM_PROMPT = """You are a Time Management Assistant. When gathering user profile information, 
ask comprehensive questions to understand:
1. User's current situation and challenges
2. Personal characteristics and strengths
3. Goals for the next period
4. Daily schedule preferences
5. Priorities and values

Be conversational, empathetic, and thorough."""


def user_profile_node(state: TimeManagementState) -> TimeManagementState:
    """
    Node 0: User Profile Collection with Interrupt Loop
    Pauses execution and gathers user profile information via interrupt.
    Collects goals, personal characteristics, and preferences.
    """
    # Generate questionnaire using LLM based on system prompt
    questionnaire_prompt = f"""{SYSTEM_PROMPT}

Based on the above context, generate a structured questionnaire for gathering user profile.
The questionnaire should have 5-7 key questions to understand the user's goals and characteristics.

Format as JSON with this structure:
{{
    "greeting": "Warm greeting message",
    "questions": [
        {{"question": "Question 1", "field": "field_name"}},
        ...
    ],
    "summary_instruction": "How to summarize responses"
}}
"""
    
    questionnaire_json = llm.invoke(questionnaire_prompt)
    
    try:
        questionnaire = json.loads(questionnaire_json)
    except json.JSONDecodeError:
        questionnaire = {
            "greeting": "Welcome! Let's set up your profile.",
            "questions": [
                {"question": "What are your main goals for the next month?", "field": "goals"},
                {"question": "What are your key strengths?", "field": "strengths"},
                {"question": "What challenges do you face?", "field": "challenges"},
                {"question": "What times of day are you most productive?", "field": "peak_hours"},
                {"question": "How many hours per day can you dedicate to work?", "field": "daily_hours"},
            ]
        }
    
    print(f"\n📋 Questionnaire Generated:\n{questionnaire['greeting']}\n")
    
    # Pause execution and wait for user responses via interrupt
    user_responses = interrupt({
        "type": "user_profile_questionnaire",
        "instruction": questionnaire['greeting'],
        "questions": questionnaire["questions"],
        "guidance": SYSTEM_PROMPT
    })
    
    # Process responses and populate state
    if user_responses:
        # Parse responses and create Goal objects
        goals_text = user_responses.get("goals", "")
        if goals_text:
            goal = Goal(
                goal_id="goal_1",
                title=goals_text.split('\n')[0] if goals_text else "User Goal",
                description=goals_text,
                frequency="weekly",
                status="active",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                priority=1
            )
            state["goals"] = [goal]
        
        # Store personal characteristics
        state["personal_characteristics"] = {
            "strengths": user_responses.get("strengths", ""),
            "challenges": user_responses.get("challenges", ""),
            "peak_hours": user_responses.get("peak_hours", ""),
            "daily_hours": user_responses.get("daily_hours", ""),
        }
        
        state["user_name"] = user_responses.get("name", "User")
        state["current_input"] = f"Profile setup complete: {user_responses.get('goals', '')}"
    
    state["action_taken"] = "user_profile_collected"
    state["last_sync_with_db"] = datetime.now().isoformat()
    
    print(f"✅ User Profile Updated with responses")
    
    return state


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
        
        # Store the SQL query in a custom field for the next node
        return {
            **state,
            "sql_query": parsed.get("sql_query", ""),
            "intent": parsed.get("intent", "select"),
        }
    except json.JSONDecodeError:
        print(f"❌ Failed to parse LLM response")
        state["action_taken"] = "failed_to_parse_intent"
        state["next_step"] = "handle_error"
        return {
            **state,
            "sql_query": "",
            "intent": "error",
        }


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
    state["sql_result"] = "PLACEHOLDER_RESULT"
    
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
