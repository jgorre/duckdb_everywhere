with latest_round_result as (
    select
        tick_id,
        producer_id,
        consumer_count,
        market_share,
        avg_enticement,
        median_enticement
    from {{ ref('pancake_simulation__producer_round_stats') }} prs
    where prs.tick_id = (select latest_tick_id from {{ ref('stg_pancake_simulation__latest_tick') }})
),

final as (
    select
        l.tick_id,
        l.producer_id,
        p.name as producer_name,
        l.consumer_count,
        l.market_share,
        l.avg_enticement,
        l.median_enticement
    from latest_round_result l
    join {{ ref('pancake_simulation__producers') }} p
    on l.producer_id = p.id
)

select * from final