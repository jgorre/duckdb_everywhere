"""
Extract Pancake Agents simulation data to Iceberg via Lakekeeper.

This bypasses the normal pipeline to allow direct inspection of simulation data.
"""

import duckdb
import os

# Lakekeeper/Iceberg config
LOCAL_TESTING_LAKEKEEPER_URI = "http://localhost:8181/catalog"
LOCAL_TESTING_MINIO_ENDPOINT = "http://192.168.64.2:30900"
LAKEKEEPER_URI = os.getenv("LAKEKEEPER_URI", LOCAL_TESTING_LAKEKEEPER_URI)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", LOCAL_TESTING_MINIO_ENDPOINT)
WAREHOUSE = os.getenv("WAREHOUSE", "iceberg-lakehouse-local")

# Source DuckDB file
DUCKDB_PATH = "pancake_world.duckdb"

# All tables to extract
TABLES = [
    "producers",
    "consumers", 
    "toppings",
    "ticks",
    "producer_offerings",
    "producer_toppings",
    "consumer_choices",
    "producer_round_stats",
]

SCHEMA_NAME = "pancake_simulation"


def main():
    print(f"🥞 Extracting pancake simulation data to Iceberg...")
    print(f"   Source: {DUCKDB_PATH}")
    print(f"   Destination: {WAREHOUSE}.{SCHEMA_NAME}")
    print(f"   Lakekeeper: {LAKEKEEPER_URI}")
    
    # Connect to local DuckDB file
    with duckdb.connect(DUCKDB_PATH, read_only=True) as source_con:
        # Check tables exist
        existing_tables = [row[0] for row in source_con.execute("SHOW TABLES").fetchall()]
        print(f"\n📋 Found tables in source: {existing_tables}")
        
        # Get row counts
        for table in TABLES:
            if table in existing_tables:
                count = source_con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"   {table}: {count} rows")
    
    # Use separate connection for Iceberg operations
    with duckdb.connect() as con:
        print(f"\n🔌 Connecting to Lakekeeper...")
        con.execute(f"""
            INSTALL iceberg;
            LOAD iceberg;
            
            ATTACH '{WAREHOUSE}' AS lakekeeper_catalog (
                TYPE iceberg,
                ENDPOINT '{LAKEKEEPER_URI}',
                AUTHORIZATION_TYPE 'none'
            );
        """)
        
        # Create schema
        print(f"\n📁 Creating schema: {SCHEMA_NAME}")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS lakekeeper_catalog.{SCHEMA_NAME};")
        
        # Attach source DuckDB as a separate database
        con.execute(f"ATTACH '{DUCKDB_PATH}' AS source_db (READ_ONLY);")
        
        # Extract each table
        print(f"\n🚀 Extracting tables...")
        for table in TABLES:
            try:
                # Check if table exists in source
                exists = con.execute(f"""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_catalog = 'source_db' AND table_name = '{table}'
                """).fetchone()[0]
                
                if exists == 0:
                    print(f"   ⏭️  {table}: skipped (not found in source)")
                    continue
                
                # Drop existing table in Iceberg
                con.execute(f"DROP TABLE IF EXISTS lakekeeper_catalog.{SCHEMA_NAME}.{table};")
                
                # Create table from source
                con.execute(f"""
                    CREATE TABLE lakekeeper_catalog.{SCHEMA_NAME}.{table} AS 
                    SELECT * FROM source_db.{table};
                """)
                
                # Verify
                count = con.execute(f"SELECT COUNT(*) FROM lakekeeper_catalog.{SCHEMA_NAME}.{table}").fetchone()[0]
                print(f"   ✅ {table}: {count} rows extracted")
                
            except Exception as e:
                print(f"   ❌ {table}: failed - {e}")
    
    print(f"\n✨ Extraction complete! Data available at lakekeeper_catalog.{SCHEMA_NAME}.*")


if __name__ == "__main__":
    main()
