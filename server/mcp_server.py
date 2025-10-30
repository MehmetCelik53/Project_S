import sqlite3
import os

from loguru import logger
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MCP Server")

# Current database file
current_db = "./database.db"

@mcp.tool()
def create_database(db_name: str) -> str:
    """Create a new SQLite database file.
    
    Args:
        db_name: Name of the database file (without .db extension)
        
    Returns:
        Success message
    """
    global current_db
    db_file = f"./{db_name}.db"
    
    try:
        # Create new database file
        conn = sqlite3.connect(db_file)
        conn.close()
        current_db = db_file
        logger.info(f"Created new database: {db_file}")
        return f"Database '{db_name}.db' created successfully."
    except Exception as e:
        return f"Error creating database: {str(e)}"

@mcp.tool()
def switch_database(db_name: str) -> str:
    """Switch to a different database file.
    
    Args:
        db_name: Name of the database file (without .db extension)
        
    Returns:
        Success message
    """
    global current_db
    db_file = f"./{db_name}.db"
    
    if not os.path.exists(db_file):
        return f"Error: Database '{db_name}.db' does not exist."
    
    current_db = db_file
    logger.info(f"Switched to database: {db_file}")
    return f"Switched to database '{db_name}.db'."

@mcp.tool()
def query_data(sql: str) -> str:
    """Execute SQL queries on the current SQLite database.
    
    This tool directly executes SQL statements (CREATE, INSERT, SELECT, UPDATE, DELETE) 
    on the current database file. Use this for ALL database operations.
    
    Args:
        sql: The SQL query to execute (e.g., CREATE TABLE, INSERT INTO, SELECT, etc.)
        
    Returns:
        Query results or success message
    """
    logger.info(f"Executing SQL query on {current_db}: {sql}")
    conn = sqlite3.connect(current_db)
    try:
        cursor = conn.execute(sql)
        conn.commit()
        
        # For SELECT queries, return results
        if sql.strip().upper().startswith("SELECT"):
            result = cursor.fetchall()
            if result:
                return "\n".join(str(row) for row in result)
            else:
                return "Query returned no results."
        # For other queries (CREATE, INSERT, UPDATE, DELETE)
        else:
            affected = cursor.rowcount
            return f"Query executed successfully. Rows affected: {affected}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        conn.close()

@mcp.prompt()
def example_prompt(code: str) -> str:
    return f"Please review this code: \n\n{code}"

if __name__ == "__main__":
    print("Starting server...")
    mcp.run(transport="stdio")
