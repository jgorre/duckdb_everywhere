with pancakes as (
    select * from {{ ref('src_postgres__pancakes_raw')}}
),

final as (
    select
        id,
        name,
        fluffiness_level,
        magical_factor
    from pancakes
)

select * from final