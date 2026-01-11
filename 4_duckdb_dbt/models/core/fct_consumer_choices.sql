with consumer_choices as (

    select
        tick_id,
        producer_id,
        consumer_id,
        enticement_score
    from {{ ref('stg_pancake_simulation__consumer_choices') }}

)

select * from consumer_choices