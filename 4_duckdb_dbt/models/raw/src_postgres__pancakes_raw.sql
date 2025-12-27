with raw as (
    select * from {{ source('pancakes_postgres', 'pancakes')}}
)

select * from raw