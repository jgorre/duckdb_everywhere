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

duckdb.sql(f"""
    INSTALL postgres;
    LOAD postgres;
           
    ATTACH 'dbname=happy_pancakes user={DB_USER} password={DB_PASSWORD} port=30042 host=102.168.64.1' AS postgres_db (TYPE postgres);

    select count(*) from postgres_db.pancakes limit 10;
""").show()