with raw_producer_toppings as (
    select
        tick_id,
        producer_id,
        topping_id
    from {{ ref('pancake_simulation__producer_toppings') }}
),

toppings as (
    select
        topping_id,
        topping_name,
        topping_category
    from {{ ref('stg_pancake_simulation__classified_toppings') }}
),

final as (
    select
        rpt.tick_id,
        rpt.producer_id,
        rpt.topping_id,
        t.topping_name,
        t.topping_category
    from raw_producer_toppings rpt
    left join toppings t on rpt.topping_id = t.topping_id
)

select * from final