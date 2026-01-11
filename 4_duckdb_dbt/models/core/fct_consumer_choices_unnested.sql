with consumer_choices as (

    select
        tick_id,
        producer_id,
        consumer_id
    from {{ ref('fct_consumer_choices') }}

),

producer_offerings as (

    select
        tick_id,
        producer_id,
        topping_id,
        topping_name,
        topping_category
    from {{ ref('fct_producer_offering_history') }}

),

final as (

    select
        cc.tick_id,
        cc.consumer_id,
        cc.producer_id,
        po.topping_id,
        po.topping_name,
        po.topping_category
    from consumer_choices cc
    left join producer_offerings po
        on cc.tick_id = po.tick_id
        and cc.producer_id = po.producer_id

)

select * from final