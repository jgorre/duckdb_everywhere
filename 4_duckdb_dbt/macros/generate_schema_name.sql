{% macro generate_schema_name(custom_schema_name, node) -%}

    {#- Use the custom schema name if provided, otherwise use target schema -#}
    {%- if custom_schema_name is not none -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}

{%- endmacro %}
