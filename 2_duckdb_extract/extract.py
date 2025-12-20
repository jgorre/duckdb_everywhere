import duckdb
import os

DB_USER = "pancake_db_reader_writer"
DB_PASSWORD = "supersecretpasswordoftheages"
DB_HOST = os.getenv("DB_HOST", "local-postgres-rw")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "happy_pancakes")

LOCAL_TESTING_LAKEKEEPER_URI = "http://localhost:8181/catalog"
LOCAL_TESTING_MINIO_ENDPOINT = "http://192.168.64.2:30900"
LAKEKEEPER_URI = os.getenv("LAKEKEEPER_URI", LOCAL_TESTING_LAKEKEEPER_URI)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", LOCAL_TESTING_MINIO_ENDPOINT)
WAREHOUSE = os.getenv("WAREHOUSE", "iceberg-lakehouse-local")


with duckdb.connect() as con:
    con.execute(f"""
        INSTALL postgres;
        LOAD postgres;    
        INSTALL iceberg;
        LOAD iceberg;

        ATTACH 'dbname=happy_pancakes user={DB_USER} password={DB_PASSWORD} port=30042 host=192.168.64.2' AS postgres_db (TYPE postgres);
        
        ATTACH '{WAREHOUSE}' AS lakekeeper_catalog (
            TYPE iceberg,
            ENDPOINT '{LAKEKEEPER_URI}',
            AUTHORIZATION_TYPE 'none'
        );    
    """)

    con.execute(f"""   
        CREATE SCHEMA IF NOT EXISTS lakekeeper_catalog.pancake_analytics;
        
        DROP TABLE IF EXISTS lakekeeper_catalog.pancake_analytics.pancakes;
        
        CREATE TABLE lakekeeper_catalog.pancake_analytics.pancakes AS 
        SELECT * FROM postgres_db.pancakes;
    """)

print("✨ Pipeline complete! Pancake data extracted to Iceberg via Lakekeeper ✨")

