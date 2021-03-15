-- https://www.holistics.io/blog/calculate-cohort-retention-analysis-with-sql/

-- (cohort_month, user_id), each
WITH cohort_items AS (
    SELECT
        date_trunc('month', U.created_at)::date AS cohort_month,
        xid AS user_id
    FROM
        users U
    ORDER BY
        1,
        2
),

-- (user_id, month_number): user X has activity in month number X
user_activities AS (
    SELECT
        A.xid AS user_id,
        (EXTRACT(epoch FROM (
                    SELECT
                        (AGE(date_trunc('month', A.updated_at)::date, C.cohort_month)))) / 2592000)::int AS month_number
    FROM
        users A
        LEFT JOIN cohort_items C ON A.xid = C.user_id
    GROUP BY
        1,
        2
),

-- (cohort_month, num_users)
cohort_size AS (
    SELECT
        cohort_month,
        count(1) AS num_users
    FROM
        cohort_items
    GROUP BY
        1
    ORDER BY
        1
),

-- (cohort_month, month_number, num_users)
B AS (
    SELECT
        C.cohort_month,
        A.month_number,
        count(1) AS num_users
    FROM
        user_activities A
        LEFT JOIN cohort_items C ON A.user_id = C.user_id
    GROUP BY
        1,
        2
),

-- (cohort_month, total_users, month_number, remaining_users)
retention AS (
    SELECT
        B.cohort_month,
        S.num_users AS total_users,
        B.month_number,
        -- B.num_users::float * 100 / S.num_users AS percentage
        B.num_users AS remaining_users
    FROM
        B
    LEFT JOIN cohort_size S ON B.cohort_month = S.cohort_month
    WHERE
        B.cohort_month IS NOT NULL
    ORDER BY
        1,
        3
)

SELECT * FROM retention;
