select * from {{ source('pancake_simulation', 'producer_round_stats') }}
