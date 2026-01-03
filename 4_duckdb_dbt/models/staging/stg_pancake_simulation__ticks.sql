with source as (

    select * from {{ ref('pancake_simulation__ticks') }}

),

renamed as (

    select
        id as tick_id,
        started_at as tick_started_at,
        completed_at as tick_completed_at
    from source

)

select * from renamed