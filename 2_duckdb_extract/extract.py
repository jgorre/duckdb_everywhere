import duckdb
import os

DB_USER = "pancake_db_reader_writer"
DB_PASSWORD = "supersecretpasswordoftheages"
DB_HOST = os.getenv("DB_HOST", "local-postgres-rw")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "happy_pancakes")

duckdb.sql("SELECT 'Hello, DuckDB!' AS greeting").show()

# duckdb.sql("select * from '2_duckdb_extract/sample_data.csv'").show()

# con = duckdb.connect('testdb.duckdb')
# con.sql("CREATE TABLE test (i INTEGER, j INTEGER)")
# con.sql("INSERT INTO test VALUES (1, 2), (3, 4), (5, 6)")
# result = con.sql("SELECT * FROM test").fetchall()
# print(result)
# con.close()

# duckdb.sql("SELECT 42").write_parquet("output.parquet")

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
# LAKEKEEPER_URI = os.getenv("LAKEKEEPER_URI", "http://localhost:8181/catalog")
# MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://192.168.64.2:30900")

# Actual in-cluster service addresses
LAKEKEEPER_URI = os.getenv("LAKEKEEPER_URI", "http://my-lakekeeper.default.svc.cluster.local:8181/catalog")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio.default.svc.cluster.local:9000")

MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin123")

duckdb.sql(f"""
    INSTALL iceberg;
    LOAD iceberg;
    
    -- Create S3 secret for MinIO (where Iceberg stores data files)
    CREATE SECRET minio_s3_secret (
        TYPE S3,
        KEY_ID '{MINIO_ACCESS_KEY}',
        SECRET '{MINIO_SECRET_KEY}',
        REGION 'us-east-1',
        ENDPOINT '{MINIO_ENDPOINT}',
        USE_SSL false,
        URL_STYLE 'path'
    );
    
    -- Attach to Lakekeeper REST Iceberg catalog
    ATTACH 'iceberg-lakehouse' AS lakekeeper_catalog (
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