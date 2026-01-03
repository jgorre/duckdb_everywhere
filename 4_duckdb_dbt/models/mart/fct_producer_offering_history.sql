with producer_toppings as (

    select
        tick_id,
        producer_id,
        topping_id
    from {{ ref('stg_pancake_simulation__producer_toppings') }}

),

toppings as (

    select
        topping_id,
        topping_name,
        topping_category
    from {{ ref('stg_pancake_simulation__toppings') }}

),

final as (

    select
        pt.tick_id,
        pt.producer_id,
        pt.topping_id,
        t.topping_name,
        t.topping_category
    from producer_toppings pt
    left join toppings t on pt.topping_id = t.topping_id

)

select * from final