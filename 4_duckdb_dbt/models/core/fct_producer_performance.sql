with producer_round_stats as (

    select
        producer_id,
        tick_id,
        consumer_count,
        market_share
    from {{ ref('stg_pancake_simulation__producer_round_stats') }}

)

select * from producer_round_stats