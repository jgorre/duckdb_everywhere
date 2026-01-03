with source as (

    select * from {{ ref('pancake_simulation__producer_round_stats') }}

),

renamed as (

    select
        tick_id,
        producer_id,
        consumer_count,
        market_share,
        avg_enticement,
        median_enticement
    from source

)

select * from renamed