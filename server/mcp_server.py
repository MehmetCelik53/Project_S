import sqlite3
import os
from pathlib import Path

from loguru import logger
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MCP Server")

# Database directory path
DATABASES_DIR = "./databases"

# Create databases directory if it doesn't exist
Path(DATABASES_DIR).mkdir(exist_ok=True)

# Current database file (None means no database selected)
current_db = None

def get_db_path(db_name: str) -> str:
    """Get full path for a database file."""
    return os.path.join(DATABASES_DIR, f"{db_name}.db")

def get_db_name_from_path(db_path: str) -> str:
    """Extract database name from path."""
    return os.path.basename(db_path).replace(".db", "")

@mcp.tool()
def list_databases() -> str:
    """List all available SQLite databases in the databases folder.
    
    Returns:
        List of database names and current active database
    """
    db_files = []
    
    # Check if databases directory exists
    if os.path.exists(DATABASES_DIR):
        db_files = [f.replace(".db", "") for f in os.listdir(DATABASES_DIR) if f.endswith(".db")]
    
    if not db_files:
        return "No databases found in the databases folder."
    
    db_list = "\n".join([f"  • {db}" for db in sorted(db_files)])
    current_status = f"\nCurrent database: {get_db_name_from_path(current_db)}" if current_db else "\n⚠️ No database selected. Use switch_database() to select one."
    
    return f"Available databases ({len(db_files)}):\n{db_list}{current_status}"

@mcp.tool()
def create_database(db_name: str) -> str:
    """Create a new SQLite database file in the databases folder.
    
    Args:
        db_name: Name of the database file (without .db extension)
        
    Returns:
        Success message
    """
    global current_db
    db_file = get_db_path(db_name)
    
    try:
        # Create new database file
        conn = sqlite3.connect(db_file)
        conn.close()
        current_db = db_file
        logger.info(f"Created new database: {db_file}")
        return f"Database '{db_name}.db' created successfully in databases/ folder. Now using: {db_name}"
    except Exception as e:
        logger.error(f"Error creating database: {str(e)}")
        return f"Error creating database: {str(e)}"

@mcp.tool()
def switch_database(db_name: str) -> str:
    """Switch to a different database file in the databases folder.
    
    Args:
        db_name: Name of the database file (without .db extension)
        
    Returns:
        Success message
    """
    global current_db
    db_file = get_db_path(db_name)
    
    if not os.path.exists(db_file):
        return f"Error: Database '{db_name}.db' does not exist in databases/ folder."
    
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
    if current_db is None:
        return "Error: No database selected. Use list_databases() to see available databases, then switch_database() to select one."
    
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
        logger.error(f"SQL Error: {str(e)}")
        return f"Error: {str(e)}"
    finally:
        conn.close()

@mcp.prompt()
def example_prompt(code: str) -> str:
    return f"Please review this code: \n\n{code}"

if __name__ == "__main__":
    print("Starting server...")
    mcp.run(transport="stdio")