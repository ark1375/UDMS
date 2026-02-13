{{ config(
    materialized = 'table',
    schema = 'silver',
    alias = 'TransactionFact'
) }}

with src as (
    select

        replace(nullif(trim("Customer ID"), 'null'), '"', '') as customer_id,
        replace(nullif(trim("Booking ID"), 'null'), '"', '') as booking_id,

        nullif(trim("Booking Status"), 'null') as booking_status,
        nullif(trim("Vehicle Type"), 'null') as vehicle_type,
        nullif(trim("Payment Method"), 'null') as payment_method,

        try_cast(nullif(trim("Booking Value"), 'null') as double) as booking_value,
        try_cast(nullif(trim("Ride Distance"), 'null') as double) as ride_distance,
        try_cast(nullif(trim("Driver Ratings"), 'null') as double) as driver_rating,
        try_cast(nullif(trim("Customer Rating"), 'null') as double) as customer_rating,

        nullif(trim("Date"), 'null') as trip_date,
        nullif(trim("Time"), 'null') as trip_time,

        nullif(trim("Reason for cancelling by Customer"), 'null') as cancel_reason_customer,
        nullif(trim("Driver Cancellation Reason"), 'null') as cancel_reason_driver,
        nullif(trim("Incomplete Rides Reason"), 'null') as incomplete_reason

    from {{ ref('transactions') }}
),

final as (
    select
        customer_id || '|' || booking_id as transaction_id,

        customer_id,
        booking_id,

        strptime(
            nullif(trim(trip_date), 'null') || ' ' ||
            nullif(trim(trip_time), 'null'),
            '%m/%d/%Y %H:%M:%S'
        ) as trip_ts,

        booking_status,
        vehicle_type,
        payment_method,

        booking_value,
        ride_distance,
        driver_rating,
        customer_rating,

        case
            when booking_status = 'Cancelled by Customer' then cancel_reason_customer
            when booking_status = 'Cancelled by Driver' then cancel_reason_driver
            when booking_status = 'Incomplete' then incomplete_reason
            else null
        end as trip_undone_reason,

        case
            when booking_status = 'Cancelled by Customer' then 'customer_cancel'
            when booking_status = 'Cancelled by Driver' then 'driver_cancel'
            when booking_status = 'Incomplete' then 'incomplete'
            else null
        end as trip_undone_reason_type

    from src
)

select * from final
