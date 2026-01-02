with raw_consumer_choices as (
    select
        tick_id,
        consumer_id,
        producer_id
    from {{ ref('pancake_simulation__consumer_choices') }}
),

raw_consumers as (
    select
        id as consumer_id,
        openness,
        pickiness,
        impulsivity,
        indulgence,
        nostalgia
    from {{ ref('pancake_simulation__consumers') }}
),

final as (
    select
        rcc.tick_id,
        rcc.consumer_id,
        rcc.producer_id,
        rc.openness,
        rc.pickiness,
        rc.impulsivity,
        rc.indulgence,
        rc.nostalgia
    from raw_consumer_choices rcc
    left join raw_consumers rc
        on rcc.consumer_id = rc.consumer_id
)

select * from final