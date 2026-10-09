{#
  Nama skema dipakai apa adanya (raw, stg, mart), bukan digabung dengan target.schema.
  Architecture.md 4.3.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {%- if custom_schema_name is none -%}
    {{ target.schema }}
  {%- else -%}
    {{ custom_schema_name | trim }}
  {%- endif -%}
{%- endmacro %}
