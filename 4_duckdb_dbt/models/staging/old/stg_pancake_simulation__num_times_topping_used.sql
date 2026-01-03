with all_time_producer_toppings as (
    select
        topping_name,
        times_topping_used_count
    from {{ ref('stg_pancake_simulation__all_time_producer_toppings') }}
),

final as (
    select
        topping_name,
        cast(sum(times_topping_used_count) as int) as num_times_topping_used
    from all_time_producer_toppings
    group by topping_name
)

select * from final