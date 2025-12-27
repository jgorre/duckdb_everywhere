import duckdb
import os

LOCAL_TESTING_LAKEKEEPER_URI = "http://localhost:8181/catalog"
LOCAL_TESTING_MINIO_ENDPOINT = "http://192.168.64.2:30900"
LAKEKEEPER_URI = os.getenv("LAKEKEEPER_URI", LOCAL_TESTING_LAKEKEEPER_URI)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", LOCAL_TESTING_MINIO_ENDPOINT)
WAREHOUSE = os.getenv("WAREHOUSE", "iceberg-lakehouse-local")


with duckdb.connect() as con:
    con.execute(f"""
        INSTALL iceberg;
        LOAD iceberg;
        
        ATTACH '{WAREHOUSE}' AS lakekeeper_catalog (
            TYPE iceberg,
            ENDPOINT '{LAKEKEEPER_URI}',
            AUTHORIZATION_TYPE 'none'
        );    
    """)
    con.execute(f"""   
        DROP TABLE IF EXISTS lakekeeper_catalog.pancake_analytics.pancakes;
        DROP TABLE IF EXISTS lakekeeper_catalog.pancake_analytics.stg_pancakes;
        DROP TABLE IF EXISTS lakekeeper_catalog.pancake_analytics.src_postgres__pancakes_raw;

        DROP TABLE IF EXISTS lakekeeper_catalog.main.pancakes;
        DROP TABLE IF EXISTS lakekeeper_catalog.main.stg_pancakes;
        DROP TABLE IF EXISTS lakekeeper_catalog.main.src_postgres__pancakes_raw;                
    """)
print("✨ Pipeline nuked! ✨")

