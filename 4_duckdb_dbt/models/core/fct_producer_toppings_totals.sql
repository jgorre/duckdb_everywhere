with producer_toppings_offerings as (

    select
        tick_id,
        producer_id,
        topping_id,
        topping_name,
        topping_category
    from {{ ref('fct_producer_offering_history') }}

),

aggregated as (

    select
        producer_id,
        topping_id,
        topping_name,
        topping_category,
        count(distinct tick_id) as total_offered_ticks,
        min(tick_id) as first_offered_tick,
        max(tick_id) as last_offered_tick,
        cast(sum(count(distinct tick_id)) over (partition by topping_category) as int) as category_total_offered_ticks
    from producer_toppings_offerings
    group by
        producer_id,
        topping_id,
        topping_name,
        topping_category

)

select * from aggregated