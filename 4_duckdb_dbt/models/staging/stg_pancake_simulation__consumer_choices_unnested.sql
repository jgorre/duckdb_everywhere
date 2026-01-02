with producer_toppings as (
    select
        tick_id,
        producer_id,
        topping_id,
        topping_name,
        topping_category
    from {{ ref('stg_pancake_simulation__producer_toppings') }}
),

final as (
    select
        cc.tick_id,
        cc.consumer_id,
        pt.producer_id,
        pt.topping_id,
        pt.topping_name,
        pt.topping_category
    from {{ ref('pancake_simulation__consumer_choices') }} cc
    left join producer_toppings pt
        on cc.tick_id = pt.tick_id
        and cc.producer_id = pt.producer_id
)

select * from final