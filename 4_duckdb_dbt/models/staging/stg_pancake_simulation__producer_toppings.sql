with source as (

    select * from {{ ref('pancake_simulation__producer_toppings') }}

),

renamed as (

    select
        tick_id,
        producer_id,
        topping_id
    from source

)

select * from renamed