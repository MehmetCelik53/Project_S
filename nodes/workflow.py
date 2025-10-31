"""
Clean SQL Agent Workflow for LangGraph
Simple linear flow: input -> classify -> execute -> respond
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from .state_schemas import TimeManagementState, create_initial_state
from .sql_nodes import (
    user_profile_node,
    user_input_node,
    classify_intent_node,
    execute_sql_node,
    generate_response_node
)


def create_sql_agent_workflow():
    """
    Create the SQL Agent workflow graph.
    
    Flow:
    START -> user_profile -> user_input -> classify_intent -> execute_sql -> generate_response -> END
    """
    
    workflow = StateGraph(TimeManagementState)
    
    # Add nodes
    workflow.add_node("user_profile", user_profile_node)
    workflow.add_node("user_input", user_input_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("generate_response", generate_response_node)
    
    # Add edges (linear flow)
    workflow.add_edge(START, "user_profile")
    workflow.add_edge("user_profile", "user_input")
    workflow.add_edge("user_input", "classify_intent")
    workflow.add_edge("classify_intent", "execute_sql")
    workflow.add_edge("execute_sql", "generate_response")
    workflow.add_edge("generate_response", END)
    
    # Compile with memory checkpointer for persistence
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    return app


# Create the app instance
sql_agent = create_sql_agent_workflow()

if __name__ == "__main__":
    # Test the workflow
    initial_state = create_initial_state(
        user_id="test_user",
        user_name="Test User",
        db_path="./databases/test.db"
    )
    
    # Add a test input
    initial_state["current_input"] = "Show me all tables in the database"
    
    print("🚀 Starting SQL Agent Workflow...")
    print("=" * 50)
    
    # Run the workflow with thread_id config
    result = sql_agent.invoke(
        initial_state,
        config={"configurable": {"thread_id": "test_thread"}}
    )
    
    print("=" * 50)
    print("✅ Workflow completed!")
    print(f"Last action: {result.get('action_taken')}")
    print(f"Messages: {result.get('messages')}")