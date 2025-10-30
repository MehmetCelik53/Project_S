import asyncio
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

load_dotenv()


# Local LLM client (OpenAI-compatible API)
llm_client = AsyncOpenAI(
    base_url="http://localhost:1234/v1",  # LM Studio veya Ollama için
    api_key="not-needed"  # Lokal LLM için API key gerekmez
)


# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python",  # Executable
    args=["./mcp_server.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)


@dataclass
class Chat:
    messages: list[dict[str, Any]] = field(default_factory=list)

    system_prompt: str = """You are a master SQLite assistant. 
    Your job is to use the tools at your disposal to execute SQL queries and provide the results to the user."""

    async def process_query(self, session: ClientSession, query: str) -> None:
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

        # Initial LLM API call
        res = await llm_client.chat.completions.create(
            model="gpt-oss:20b",
            messages=[
                {"role": "system", "content": self.system_prompt},
                *self.messages
            ],
            tools=available_tools,
            tool_choice="auto",
        )

        assistant_message = res.choices[0].message
        
        # Handle text response
        if assistant_message.content:
            print(assistant_message.content)
            self.messages.append({
                "role": "assistant",
                "content": assistant_message.content
            })
        
        # Handle tool calls
        if assistant_message.tool_calls:
            # Add assistant message with tool calls to history
            self.messages.append({
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
                import json
                tool_args = json.loads(tool_call.function.arguments)

                # Execute tool call via MCP
                result = await session.call_tool(tool_name, tool_args)
                
                # Add tool result to messages
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": getattr(result.content[0], "text", ""),
                })
            
            # Get next response from LLM with tool results
            res = await llm_client.chat.completions.create(
                model="gpt-oss:20b",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *self.messages
                ],
                tools=available_tools,
            )
            
            final_response = res.choices[0].message.content
            if final_response:
                self.messages.append({
                    "role": "assistant",
                    "content": final_response
                })
                print(final_response)

    async def chat_loop(self, session: ClientSession):
        while True:
            query = input("\nQuery: ").strip()
            self.messages.append({
                "role": "user",
                "content": query,
            })

            await self.process_query(session, query)

    async def run(self):
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()

                await self.chat_loop(session)


chat = Chat()

asyncio.run(chat.run())
