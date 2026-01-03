with source as (

    select * from {{ ref('pancake_simulation__consumers') }}

),

renamed as (

    select
        id as consumer_id,
        openness,
        pickiness,
        impulsivity,
        indulgence,
        nostalgia
    from source

)

select * from renamed
