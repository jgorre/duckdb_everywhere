with raw as (
    select * from {{ source('lakekeeper_catalog', 'pancakes')}}
),

final as (
    select
        id,
        name,
        fluffiness_level,
        magical_factor
    from raw
)

select * from final