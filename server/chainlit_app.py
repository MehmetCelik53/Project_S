import json
from typing import Any

import chainlit as cl
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

load_dotenv()

# Local LLM client (OpenAI-compatible API)
llm_client = AsyncOpenAI(
    base_url="http://localhost:11434/v1",  # Ollama 
    # base_url="http://localhost:1234/v1",  # LM Studio 
    api_key="not-needed"  # no need for API key for local LLM
)

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["server/mcp_server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)

SYSTEM_PROMPT = """You are a SQLite assistant. Execute commands EXACTLY as requested, nothing more.

STRICT RULES:
1. ALWAYS use tools - NEVER just show code
2. Do EXACTLY what the user asks - no suggestions, no questions, no extra features
3. Keep responses SHORT - just confirm what was done
4. When user asks about databases, ALWAYS use list_databases() tool first

Available operations:
- "how many databases" or "list databases" -> use list_databases tool
- "create database X" -> use create_database tool
- "switch to database X" -> use switch_database tool
- "create table X" -> use query_data with CREATE TABLE (id INTEGER PRIMARY KEY, name TEXT)
- "add/insert X" -> use query_data with INSERT
- "show/list/select" -> use query_data with SELECT

Do the task. Nothing else."""


@cl.on_chat_start
async def start():
    """Initialize MCP session when chat starts"""
    try:
        # Start MCP server connection
        stdio_ctx = stdio_client(server_params)
        read, write = await stdio_ctx.__aenter__()
        
        session_ctx = ClientSession(read, write)
        session = await session_ctx.__aenter__()
        await session.initialize()
        
        # Store session and contexts in user session
        cl.user_session.set("mcp_session", session)
        cl.user_session.set("stdio_ctx", stdio_ctx)
        cl.user_session.set("session_ctx", session_ctx)
        cl.user_session.set("messages", [])
        
        await cl.Message(
            content="**SQLite Assistant Ready!**\n\nBen SQL sorgularınızı çalıştırabilen bir asistanım. Veritabanınızla ilgili sorularınızı sorabilirsiniz."
        ).send()
    except Exception as e:
        await cl.Message(
            content=f"**Error starting MCP session:** {str(e)}\n\nLütfen MCP server'ının çalıştığından emin olun."
        ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    session: ClientSession = cl.user_session.get("mcp_session")
    messages: list[dict[str, Any]] = cl.user_session.get("messages")
    
    # Check if session is properly initialized
    if not session or messages is None:
        await cl.Message(
            content="Session not initialized. Please refresh the page."
        ).send()
        return
    
    # Add user message to history
    messages.append({
        "role": "user",
        "content": message.content
    })
    
    # Get available tools from MCP server
    response = await session.list_tools()
    available_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            }
        }
        for tool in response.tools
    ]
    
    # Debug: Show available tools
    print(f"Available tools: {[t['function']['name'] for t in available_tools]}")
    
    # Create a message for streaming response
    msg = cl.Message(content="")
    await msg.send()
    
    # Initial LLM API call
    res = await llm_client.chat.completions.create(
        model="gpt-oss:20b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        tools=available_tools,
        tool_choice="auto",
    )
    
    assistant_message = res.choices[0].message
    
    # Handle text response
    if assistant_message.content:
        msg.content = assistant_message.content
        await msg.update()
        
        messages.append({
            "role": "assistant",
            "content": assistant_message.content
        })
    
    # Handle tool calls
    if assistant_message.tool_calls:
        # Show that we're executing tools
        tool_msg = cl.Message(content="**Executing SQL Query...**")
        await tool_msg.send()
        
        # Add assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })
        
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            
            # Show the SQL query being executed
            if "sql" in tool_args:
                await cl.Message(
                    content=f"```sql\n{tool_args['sql']}\n```",
                    author="SQL Query"
                ).send()

            # Execute tool call via MCP
            result = await session.call_tool(tool_name, tool_args)
            tool_result = getattr(result.content[0], "text", "")
            
            # Show tool result
            await cl.Message(
                content=f"**Result:**\n```\n{tool_result}\n```",
                author="Database"
            ).send()
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })
        
        # Get next response from LLM with tool results
        res = await llm_client.chat.completions.create(
            model="gpt-oss:20b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *messages
            ],
            tools=available_tools,
        )
        
        final_response = res.choices[0].message.content
        if final_response:
            messages.append({
                "role": "assistant",
                "content": final_response
            })
            
            # Send final response
            await cl.Message(
                content=final_response
            ).send()
    
    # Update session
    cl.user_session.set("messages", messages)


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