-- =============================================================================
-- NeuroMining — Hive Feature Engineering
-- Reads MapReduce output from HDFS and produces a consolidated feature table
-- for Spark MLlib ingestion.
-- Run via:  hive -f hive/feature_eng.sql
-- =============================================================================

-- Use a dedicated database
CREATE DATABASE IF NOT EXISTS neuromining
  LOCATION 'hdfs:///neuromining/hive/warehouse';

USE neuromining;

-- =============================================================================
-- Stage 1: External table — raw MapReduce output
--   Schema mirrors reducer output: user_id, action, count
-- =============================================================================
DROP TABLE IF EXISTS raw_action_counts;
CREATE EXTERNAL TABLE raw_action_counts (
    user_id     STRING,
    action      STRING,
    cnt         BIGINT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION 'hdfs:///neuromining/cleaned/session_counts/'
TBLPROPERTIES ('skip.header.line.count' = '0');

-- =============================================================================
-- Stage 2: Pivot action counts into feature columns
-- =============================================================================
DROP TABLE IF EXISTS user_action_pivot;
CREATE TABLE user_action_pivot
STORED AS ORC
TBLPROPERTIES ("orc.compress" = "SNAPPY")
AS
SELECT
    user_id,
    SUM(CASE WHEN action = 'search'       THEN cnt ELSE 0 END) AS n_search,
    SUM(CASE WHEN action = 'click'        THEN cnt ELSE 0 END) AS n_click,
    SUM(CASE WHEN action = 'view_profile' THEN cnt ELSE 0 END) AS n_view_profile,
    SUM(CASE WHEN action = 'send_message' THEN cnt ELSE 0 END) AS n_send_message,
    SUM(CASE WHEN action = 'comment'      THEN cnt ELSE 0 END) AS n_comment,
    SUM(CASE WHEN action = 'save_post'    THEN cnt ELSE 0 END) AS n_save_post,
    SUM(CASE WHEN action = 'share'        THEN cnt ELSE 0 END) AS n_share,
    SUM(CASE WHEN action = 'follow'       THEN cnt ELSE 0 END) AS n_follow,
    SUM(CASE WHEN action = 'login'        THEN cnt ELSE 0 END) AS n_login,
    SUM(CASE WHEN action = '__total__'    THEN cnt ELSE 0 END) AS total_actions
FROM raw_action_counts
GROUP BY user_id;

-- =============================================================================
-- Stage 3: External table — raw JSON logs for text-based features
--   Using Hive's JsonSerDe to read the gzipped JSONL directly
-- =============================================================================
DROP TABLE IF EXISTS raw_logs;
CREATE EXTERNAL TABLE raw_logs (
    `timestamp`       STRING,
    user_id           STRING,
    session_id        STRING,
    action            STRING,
    payload           STRUCT<
        query:         STRING,
        results_count: INT,
        page:          INT,
        url:           STRING,
        dwell_time_ms: INT,
        content_snippet: STRING
    >,
    client            STRUCT<
        ip:          STRING,
        user_agent:  STRING,
        country:     STRING
    >,
    schema_version    STRING
)
ROW FORMAT SERDE 'org.apache.hive.hcatalog.data.JsonSerDe'
STORED AS TEXTFILE
LOCATION 'hdfs:///neuromining/raw/clickstream/'
TBLPROPERTIES ("hive.input.format" = "org.apache.hadoop.mapred.TextInputFormat");

-- =============================================================================
-- Stage 4: Session-level aggregates using window functions
-- =============================================================================
DROP TABLE IF EXISTS session_features;
CREATE TABLE session_features
STORED AS ORC
TBLPROPERTIES ("orc.compress" = "SNAPPY")
AS
SELECT
    user_id,
    session_id,
    MIN(`timestamp`)                                          AS session_start,
    MAX(`timestamp`)                                          AS session_end,
    COUNT(*)                                                  AS session_events,

    -- Time since last action (seconds) using window LAG
    AVG(
        UNIX_TIMESTAMP(`timestamp`, "yyyy-MM-dd'T'HH:mm:ss") -
        LAG(UNIX_TIMESTAMP(`timestamp`, "yyyy-MM-dd'T'HH:mm:ss"), 1, NULL)
            OVER (PARTITION BY user_id, session_id ORDER BY `timestamp`)
    )                                                         AS avg_inter_event_sec,

    -- Session duration in minutes
    (
        UNIX_TIMESTAMP(MAX(`timestamp`), "yyyy-MM-dd'T'HH:mm:ss") -
        UNIX_TIMESTAMP(MIN(`timestamp`), "yyyy-MM-dd'T'HH:mm:ss")
    ) / 60.0                                                  AS session_duration_min,

    -- Professional keyword signal: count events with professional payloads
    SUM(
        CASE
            WHEN action = 'search' AND REGEXP_COUNT(
                LOWER(NVL(payload.query, '')),
                'machine learning|data engineer|kubernetes|spark|hadoop|mlops|'
                'neural network|microservice|ci/cd|docker|terraform|system design|'
                'database shard|stream processing|recommendation'
            ) > 0 THEN 1
            ELSE 0
        END
    )                                                         AS n_professional_searches,

    -- Engagement depth: high-dwell clicks
    SUM(
        CASE WHEN action = 'click' AND payload.dwell_time_ms > 30000 THEN 1
             ELSE 0 END
    )                                                         AS n_deep_clicks,

    -- Country (take mode via subquery later; use any() here for simplicity)
    FIRST_VALUE(client.country)
        OVER (PARTITION BY user_id, session_id ORDER BY `timestamp`)  AS country

FROM raw_logs
WHERE user_id IS NOT NULL AND session_id IS NOT NULL
GROUP BY user_id, session_id;

-- =============================================================================
-- Stage 5: Consolidated Feature Table  (joins pivot + session aggregates)
-- =============================================================================
DROP TABLE IF EXISTS feature_table;
CREATE TABLE feature_table
PARTITIONED BY (dt STRING)
STORED AS ORC
TBLPROPERTIES ("orc.compress" = "SNAPPY")
AS
SELECT
    p.user_id,

    -- Action counts
    p.n_search,
    p.n_click,
    p.n_view_profile,
    p.n_send_message,
    p.n_comment,
    p.n_save_post,
    p.n_share,
    p.n_follow,
    p.total_actions,

    -- Session-level aggregates
    COUNT(DISTINCT s.session_id)                              AS total_sessions,
    AVG(s.session_duration_min)                               AS avg_session_duration_min,
    AVG(s.session_events)                                     AS avg_events_per_session,
    AVG(s.avg_inter_event_sec)                                AS avg_inter_event_sec,
    SUM(s.n_professional_searches)                            AS total_professional_searches,
    SUM(s.n_deep_clicks)                                      AS total_deep_clicks,

    -- Derived ratio features
    CASE WHEN p.total_actions > 0
         THEN SUM(s.n_professional_searches) * 1.0 / p.total_actions
         ELSE 0.0 END                                         AS professional_ratio,

    CASE WHEN p.n_search > 0
         THEN p.n_click * 1.0 / p.n_search
         ELSE 0.0 END                                         AS click_through_rate,

    -- Label: 1 = high-value, 0 = low-value
    CASE
        WHEN SUM(s.n_professional_searches) >= 3
             AND p.n_send_message >= 1
             AND AVG(s.session_duration_min) >= 10 THEN 1
        ELSE 0
    END                                                       AS label,

    DATE_FORMAT(MIN(s.session_start), 'yyyy-MM-dd')           AS dt

FROM user_action_pivot p
JOIN session_features   s ON p.user_id = s.user_id
GROUP BY
    p.user_id, p.n_search, p.n_click, p.n_view_profile,
    p.n_send_message, p.n_comment, p.n_save_post,
    p.n_share, p.n_follow, p.total_actions;

-- =============================================================================
-- Stage 6: Export Feature Table to HDFS (Parquet) for Spark
-- =============================================================================
SET hive.exec.compress.output=true;
SET parquet.compression=SNAPPY;

INSERT OVERWRITE DIRECTORY 'hdfs:///neuromining/features/feature_table/'
STORED AS PARQUET
SELECT * FROM feature_table;

SELECT 'Feature engineering complete.' AS status;
