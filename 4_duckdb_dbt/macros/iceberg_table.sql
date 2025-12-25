{% materialization iceberg_table, adapter='duckdb' %}
  {# 
    Simplified materialization for Iceberg tables.
    Uses DROP + CREATE since Iceberg doesn't support temp tables or ALTER TABLE RENAME.
    Requires disable_transactions: true in profiles.yml for proper Iceberg behavior.
  #}
  
  {%- set target_relation = this -%}
  
  -- Drop and recreate (no temp tables, no transactions)
  {% call statement('main') -%}
    drop table if exists {{ target_relation }};
    create table {{ target_relation }} as (
      {{ sql }}
    );
  {%- endcall %}
  
  {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}
