with latest_tick as (
    select
        max(tick_id) as tick_id
    from
        {{ ref('dim_ticks') }}
), 

producer_market_share as (
    select
        tick_id,
        producer_id,
        market_share
    from
        {{ ref('fct_producer_performance') }}
),

final as (
    select
        producer_id,
        market_share
    from producer_market_share
    where tick_id = (select tick_id from latest_tick)
)

select * from final