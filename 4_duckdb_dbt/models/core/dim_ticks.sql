with ticks as (

    select
        tick_id,
        tick_started_at,
        tick_completed_at
    from {{ ref('stg_pancake_simulation__ticks') }}

)

select * from ticks