import os
from dotenv import load_dotenv
from core.sf_service import SnowflakeService
from core.logger import Logger

def main():
    load_dotenv()
    print("Testing Snowflake Connection...")
    
    sf_service = SnowflakeService()
    
    # Test connection
    conn = sf_service.get_connection()
    if conn:
        print("Successfully connected to Snowflake!")
        
        # Test simple query
        print("Executing test query: SELECT CURRENT_VERSION()")
        result = sf_service.execute_query("SELECT CURRENT_VERSION()")
        
        if result.error_message:
            print(f"Query failed: {result.error_message}")
        else:
            version = result.rows[0][0]
            print(f"Query successful! Snowflake Version: {version}")

        # List schemas in PATENTS
        print("Listing schemas in PATENTS database...")
        result = sf_service.execute_query("SHOW SCHEMAS IN DATABASE PATENTS")
        if not result.error_message:
            print(f"Schemas: {[row[1] for row in result.rows]}") # row[1] is schema name usually
        else:
            print(f"Failed to list schemas: {result.error_message}")

        # List tables in PATENTS.PATENTS
        print("Listing tables in PATENTS.PATENTS...")
        result = sf_service.execute_query("SHOW TABLES IN SCHEMA PATENTS.PATENTS")
        if not result.error_message:
            print(f"Tables count: {len(result.rows)}")
            if result.rows:
                print(f"Sample Tables: {[row[1] for row in result.rows[:5]]}")
        else:
            print(f"Failed to list tables: {result.error_message}")
    else:
        print("Failed to connect to Snowflake. Check credentials and role.")

if __name__ == "__main__":
    main()
