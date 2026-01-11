with producers as (

    select
        producer_id,
        producer_name,
        creativity_bias,
        risk_tolerance
    from {{ ref('stg_pancake_simulation__producers') }}

)

select * from producers