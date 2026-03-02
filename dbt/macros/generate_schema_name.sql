/*
  generate_schema_name
  ─────────────────────
  Override the default dbt schema naming so that schemas in Snowflake
  are created exactly as declared in dbt_project.yml (without the profile
  target prefix that dbt appends by default).

  Result: STOCK_ANALYTICS_DB.STAGING, .INTERMEDIATE, .MARTS etc.
*/

{% macro generate_schema_name(custom_schema_name, node) -%}

  {%- set default_schema = target.schema -%}

  {%- if custom_schema_name is none -%}
    {{ default_schema }}
  {%- else -%}
    {{ custom_schema_name | trim | upper }}
  {%- endif -%}

{%- endmacro %}
