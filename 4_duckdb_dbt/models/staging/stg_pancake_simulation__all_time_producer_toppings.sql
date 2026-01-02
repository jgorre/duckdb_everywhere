with producer_toppings as (
    select
        producer_id,
        topping_name,
        topping_category
    from {{ ref('stg_pancake_simulation__producer_toppings') }}
),

final as (
    select
        producer_id,
        topping_name,
        count(topping_name) as times_topping_used_count,
        topping_category
    from producer_toppings
    group by producer_id, topping_name, topping_category
)

select * from final