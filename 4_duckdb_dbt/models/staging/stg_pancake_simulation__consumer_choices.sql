with source as (
    
    select * from {{ ref('pancake_simulation__consumer_choices') }}

),

renamed as (

    select
        tick_id,
        producer_id,
        consumer_id,
        enticement_score
    from source

)

select * from renamed
