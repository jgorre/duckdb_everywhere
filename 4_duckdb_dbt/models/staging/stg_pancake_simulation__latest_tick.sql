with latest_tick_id as (
    select
        max(id) as latest_tick_id
    from {{ ref('pancake_simulation__ticks') }}
)

select latest_tick_id from latest_tick_id