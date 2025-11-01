"""
Chainlit SQL Agent Interface
Simplified integration with MCP tools
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
from nodes.sql_nodes import generate_sql_query

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

SYSTEM_PROMPT = """You are a SQLite assistant. When the user asks to execute a query, use the query_data tool.
Always respond with tool calls, not just text.
"""


@cl.on_chat_start
async def start():
    """Initialize MCP session and workflow state"""
    try:
        # Initialize MCP server connection
        stdio_ctx = stdio_client(server_params)
        read, write = await stdio_ctx.__aenter__()
        
        session_ctx = ClientSession(read, write)
        session = await session_ctx.__aenter__()
        await session.initialize()
        
        # Store in session
        cl.user_session.set("mcp_session", session)
        cl.user_session.set("stdio_ctx", stdio_ctx)
        cl.user_session.set("session_ctx", session_ctx)
        
        # Initialize state
        initial_state = create_initial_state(
            user_id=cl.user_session.get("id", "user_1"),
            user_name="SQL User",
            db_path="./databases/sql_agent.db"
        )
        initial_state["personal_characteristics"] = {
            "strengths": "",
            "challenges": "",
            "peak_hours": "",
            "daily_hours": "",
        }
        
        cl.user_session.set("workflow_state", initial_state)
        cl.user_session.set("profile_collected", False)
        
        # Collect profile
        await cl.Message(
            content="**Welcome to SQL Agent!** 👋\n\nLet me ask you a few questions:"
        ).send()
        
        profile_data = {}
        questions = [
            ("What are your main goals?", "goals"),
            ("What are your key strengths?", "strengths"),
            ("What challenges do you face?", "challenges"),
            ("When are you most productive?", "peak_hours"),
            ("How many hours daily?", "daily_hours"),
        ]
        
        for question, field in questions:
            response = await cl.AskUserMessage(
                content=question,
                timeout=300
            ).send()
            if response:
                profile_data[field] = response["content"]
        
        # Update state
        initial_state["personal_characteristics"] = profile_data
        cl.user_session.set("workflow_state", initial_state)
        cl.user_session.set("profile_collected", True)
        
        await cl.Message(
            content="✅ **Ready!** Ask me SQL questions."
        ).send()
        
    except Exception as e:
        await cl.Message(
            content=f"❌ Error: {str(e)}"
        ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle user messages"""
    
    workflow_state = cl.user_session.get("workflow_state")
    session: ClientSession = cl.user_session.get("mcp_session")
    profile_collected = cl.user_session.get("profile_collected", False)
    
    if not workflow_state or not session:
        await cl.Message(content="❌ Session not initialized.").send()
        return
    
    if not profile_collected:
        await cl.Message(content="⏳ Complete profile setup first.").send()
        return
    
    try:
        # Generate SQL
        user_input = message.content
        profile = workflow_state.get("personal_characteristics", {})
        
        sql_query = generate_sql_query(user_input, profile)
        
        if not sql_query or sql_query == "":
            await cl.Message(content="❌ Failed to generate SQL.").send()
            return
        
        # Show SQL
        await cl.Message(
            content=f"📝 **SQL:**\n```sql\n{sql_query}\n```"
        ).send()
        
        # Get MCP tools
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
        
        # Call LLM with tools
        llm_response = await llm_client.chat.completions.create(
            model="gpt-oss:20b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Execute this SQL: {sql_query}"}
            ],
            tools=available_tools,
            tool_choice="auto",
        )
        
        assistant_message = llm_response.choices[0].message
        
        # Execute tool calls
        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                result = await session.call_tool(tool_name, tool_args)
                
                # Get result content
                result_text = ""
                if result.content:
                    content_item = result.content[0]
                    if hasattr(content_item, "text"):
                        result_text = content_item.text
                    else:
                        result_text = str(content_item)
                
                await cl.Message(
                    content=f"💾 **Result:**\n```\n{result_text}\n```"
                ).send()
        else:
            if assistant_message.content:
                await cl.Message(
                    content=f"✅ {assistant_message.content}"
                ).send()
        
    except Exception as e:
        await cl.Message(content=f"❌ Error: {str(e)}").send()


@cl.on_chat_end
async def end():
    """Cleanup"""
    try:
        session = cl.user_session.get("mcp_session")
        session_ctx = cl.user_session.get("session_ctx")
        stdio_ctx = cl.user_session.get("stdio_ctx")
        
        if session_ctx:
            await session_ctx.__aexit__(None, None, None)
        if stdio_ctx:
            await stdio_ctx.__aexit__(None, None, None)
    except Exception as e:
        print(f"Cleanup error: {e}")
