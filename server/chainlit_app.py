"""
Chainlit SQL Agent Interface
Integrates LangGraph workflow with Chainlit UI and MCP tools
"""

import json
from typing import Any

import chainlit as cl
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

# Import the SQL agent workflow
import sys
sys.path.insert(0, '.')
from nodes.workflow import sql_agent
from nodes.state_schemas import create_initial_state

# Local LLM client (OpenAI-compatible API)
llm_client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="not-needed"
)

# Create server parameters for MCP stdio connection
server_params = StdioServerParameters(
    command="python",
    args=["server/mcp_server.py"],
    env=None,
)

SYSTEM_PROMPT = """You are a SQLite assistant. Execute commands EXACTLY as requested.

STRICT RULES:
1. Use available tools (list_databases, switch_database, create_database, query_data)
2. Do EXACTLY what the user asks
3. Keep responses SHORT
4. When in doubt, use list_databases() first
"""


@cl.on_chat_start
async def start():
    """Initialize MCP session and workflow state when chat starts"""
    try:
        # Initialize MCP server connection
        stdio_ctx = stdio_client(server_params)
        read, write = await stdio_ctx.__aenter__()
        
        session_ctx = ClientSession(read, write)
        session = await session_ctx.__aenter__()
        await session.initialize()
        
        # Store session in user session
        cl.user_session.set("mcp_session", session)
        cl.user_session.set("stdio_ctx", stdio_ctx)
        cl.user_session.set("session_ctx", session_ctx)
        
        # Initialize workflow state
        initial_state = create_initial_state(
            user_id=cl.user_session.get("id", "user_1"),
            user_name="SQL User",
            db_path="./databases/sql_agent.db"
        )
        cl.user_session.set("workflow_state", initial_state)
        
        await cl.Message(
            content="**SQL Agent Ready!** 🚀\n\nI'm ready to help you with SQL queries. Ask me anything about your database!"
        ).send()
        
    except Exception as e:
        await cl.Message(
            content=f"⚠️ Error starting: {str(e)}\n\nMake sure MCP server is running: `python server/mcp_server.py`"
        ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming user messages and run workflow"""
    
    # Get workflow state and MCP session
    workflow_state = cl.user_session.get("workflow_state")
    session: ClientSession = cl.user_session.get("mcp_session")
    
    if not workflow_state or not session:
        await cl.Message(
            content="❌ Session not initialized. Please refresh the page."
        ).send()
        return
    
    try:
        # Update state with user input
        workflow_state["current_input"] = message.content
        
        # Show thinking message
        thinking_msg = cl.Message(content="🤔 Processing your request...")
        await thinking_msg.send()
        
        # Run the workflow through classify_intent to generate SQL
        result_state = sql_agent.invoke(
            workflow_state,
            config={"configurable": {"thread_id": "default"}}
        )
        
        # Get the SQL query from workflow
        sql_query = result_state.get("sql_query", "")
        
        if not sql_query:
            await cl.Message(
                content="❌ Failed to generate SQL query from your request."
            ).send()
            return
        
        # Show the SQL query
        await cl.Message(
            content=f"📝 **SQL Query:**\n```sql\n{sql_query}\n```",
            author="Workflow"
        ).send()
        
        # Get available MCP tools
        tools_response = await session.list_tools()
        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                }
            }
            for tool in tools_response.tools
        ]
        
        # Call LLM with tools to execute the SQL
        llm_response = await llm_client.chat.completions.create(
            model="gpt-oss:20b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Execute this SQL query: {sql_query}"}
            ],
            tools=available_tools,
            tool_choice="auto",
        )
        
        assistant_message = llm_response.choices[0].message
        
        # Handle tool calls from LLM
        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Execute tool via MCP
                result = await session.call_tool(tool_name, tool_args)
                tool_result = getattr(result.content[0], "text", "")
                
                # Store result in workflow state
                result_state["sql_result"] = tool_result
                
                # Show result
                await cl.Message(
                    content=f"💾 **Result:**\n```\n{tool_result}\n```",
                    author="Database"
                ).send()
        
        # Run final node to generate friendly response
        final_state = sql_agent.invoke(
            result_state,
            config={"configurable": {"thread_id": "default"}}
        )
        
        # Get the generated response from messages
        final_messages = final_state.get("messages", [])
        if final_messages:
            last_response = final_messages[-1].get("content", "Query completed.")
            await cl.Message(
                content=f"✅ **Response:**\n{last_response}",
                author="Assistant"
            ).send()
        
        # Update session state
        cl.user_session.set("workflow_state", final_state)
        
    except Exception as e:
        await cl.Message(
            content=f"❌ Error: {str(e)}"
        ).send()


@cl.on_chat_end
async def end():
    """Cleanup when chat ends"""
    try:
        session: ClientSession = cl.user_session.get("mcp_session")
        session_ctx = cl.user_session.get("session_ctx")
        stdio_ctx = cl.user_session.get("stdio_ctx")
        
        if session and session_ctx:
            await session_ctx.__aexit__(None, None, None)
        if stdio_ctx:
            await stdio_ctx.__aexit__(None, None, None)
    except Exception as e:
        print(f"Error during cleanup: {e}")
