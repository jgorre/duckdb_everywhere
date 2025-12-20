import duckdb
import os

DB_USER = "pancake_db_reader_writer"
DB_PASSWORD = "supersecretpasswordoftheages"
DB_HOST = os.getenv("DB_HOST", "local-postgres-rw")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "happy_pancakes")

# duckdb.sql("SELECT 'Hello, DuckDB!' AS greeting").show()

# 1. Extract Data
duckdb.sql(f"""
    INSTALL postgres;
    LOAD postgres;
           
    ATTACH 'dbname=happy_pancakes user={DB_USER} password={DB_PASSWORD} port=30042 host=192.168.64.2' AS postgres_db (TYPE postgres);

    select * from postgres_db.pancakes;
""").show()

# How do we buffer large extracts to DuckDB?

# 2. Write data to Iceberg via Lakekeeper catalog
# Connection details for REST Iceberg catalog
# NOTE: Lakekeeper uses /catalog prefix for Iceberg REST API

# For local testing with port-forwarding
LOCAL_TESTING_LAKEKEEPER_URI = "http://localhost:8181/catalog"
LOCAL_TESTING_MINIO_ENDPOINT = "http://192.168.64.2:30900"

LAKEKEEPER_URI = os.getenv("LAKEKEEPER_URI", LOCAL_TESTING_LAKEKEEPER_URI)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", LOCAL_TESTING_MINIO_ENDPOINT)

WAREHOUSE = os.getenv("WAREHOUSE", "iceberg-lakehouse-local")

MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")

duckdb.sql(f"""
    INSTALL iceberg;
    LOAD iceberg;
    
    -- Attach to Lakekeeper REST Iceberg catalog
    ATTACH '{WAREHOUSE}' AS lakekeeper_catalog (
        TYPE iceberg,
        ENDPOINT '{LAKEKEEPER_URI}',
        AUTHORIZATION_TYPE 'none'
    );
    
    -- Create namespace (if it doesn't exist)
    CREATE SCHEMA IF NOT EXISTS lakekeeper_catalog.pancake_analytics;
    
    -- Drop table if exists, then recreate (DuckDB-Iceberg doesn't support CREATE OR REPLACE)
    DROP TABLE IF EXISTS lakekeeper_catalog.pancake_analytics.pancakes;
    
    CREATE TABLE lakekeeper_catalog.pancake_analytics.pancakes AS 
    SELECT * FROM postgres_db.pancakes;
    
    -- Verify the data was written
    SELECT COUNT(*) as total_pancakes FROM lakekeeper_catalog.pancake_analytics.pancakes;
""").show()

print("✨ Pipeline complete! Pancake data extracted to Iceberg via Lakekeeper ✨")


duckdb.sql("""
    SELECT * FROM lakekeeper_catalog.pancake_analytics.pancakes LIMIT 5;
""").show()