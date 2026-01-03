with source as (

    select * from {{ ref('pancake_simulation__producers') }}

),

renamed as (

    select
        id as producer_id,
        name as producer_name,
        creativity_bias,
        risk_tolerance
    from source

)

select * from renamed