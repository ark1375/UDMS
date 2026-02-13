{{ config(materialized='table', schema='bronze') }}

with raw as (
    select * from {{ ref('transactions') }}
)
select
    row_number() over (order by "Date") as uid,
    *
from raw;
