{% macro generate_iceberg_source(database_name, schema_name) %}

{# 1. Query specifically for the columns we need #}
{% set sql %}
    SELECT 
        database_name,
        schema_name,
        table_name
    FROM duckdb_tables()
    WHERE database_name = '{{ database_name }}'
      AND schema_name = '{{ schema_name }}'
    ORDER BY database_name, schema_name, table_name
{% endset %}

{% set results = run_query(sql) %}

{% if execute %}
    {% set yaml_output %}
version: 2

sources:
  - name: {{ schema_name }}
    tables:
    {% for row in results %}
      - name: {{ row['table_name'] }}
    {% endfor %}
    {% endset %}

    {{ log(yaml_output, info=True) }}
    
{% endif %}

{% endmacro %}