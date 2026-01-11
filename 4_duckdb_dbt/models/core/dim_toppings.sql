with toppings as (

    select
        topping_id,
        topping_name,
        topping_category
    from {{ ref('stg_pancake_simulation__toppings') }}

)

select * from toppings