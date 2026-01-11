with consumers as (

    select
        consumer_id,
        openness,
        pickiness,
        impulsivity,
        indulgence,
        nostalgia
    from {{ ref('stg_pancake_simulation__consumers') }}

)

select * from consumers