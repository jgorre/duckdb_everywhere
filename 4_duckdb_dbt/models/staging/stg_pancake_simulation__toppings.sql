with source as (

    select * from {{ ref('pancake_simulation__toppings') }}

),

renamed as (

    select
        id as topping_id,
        name as topping_name,
        case
            when topping_name in ('blueberry', 'strawberry', 'banana', 'chocolate chip', 'whipped cream') then 'standard'
            when topping_name in ('maple syrup', 'honey', 'peanut butter', 'nutella', 'caramel') then 'syrups and spreads'
            when topping_name in ('bacon', 'fried egg', 'cheddar cheese', 'goat cheese', 'prosciutto') then 'savory'
            when topping_name in ('walnut', 'pistachio', 'almond', 'black sesame', 'candied pecan') then 'nuts and seeds'
            when topping_name in ('matcha powder', 'lavender honey', 'mango', 'passion fruit', 'cardamom sugar') then 'exotic'
            else 'uncategorized'
        end as topping_category
    from source

)

select * from renamed

