with consumers as (
    select
        consumer_id,
        openness,
        pickiness,
        impulsivity,
        indulgence,
        nostalgia
    from {{ ref('dim_consumers') }}
),

consumer_choices as (
    select
        tick_id,
        consumer_id,
        producer_id
    from {{ ref('fct_consumer_choices') }}
),

final as (
    select
        cc.tick_id,
        cc.producer_id,
        c.consumer_id,
        c.openness,
        c.pickiness,
        c.impulsivity,
        c.indulgence,
        c.nostalgia,
    from consumers c
    left join consumer_choices cc
        on c.consumer_id = cc.consumer_id
)

select * from final