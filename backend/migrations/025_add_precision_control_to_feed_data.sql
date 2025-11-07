-- Migration 025: Add precision control to feed data (2 decimal places)
-- This migration converts TEXT columns to DECIMAL(10,2) for better precision control
-- and implements rounding to 2 decimal places for all numeric feed data

-- First, create a function to safely convert and round numeric values
CREATE OR REPLACE FUNCTION round_numeric_value(input_value TEXT)
RETURNS DECIMAL(10,2) AS $$
BEGIN
    -- Handle NULL, empty, or non-numeric values
    IF input_value IS NULL OR input_value = '' OR input_value = 'nan' OR input_value = 'inf' OR input_value = '-inf' THEN
        RETURN NULL;
    END IF;
    
    -- Try to convert to numeric and round to 2 decimal places
    BEGIN
        RETURN ROUND(CAST(input_value AS DECIMAL(10,4)), 2);
    EXCEPTION
        WHEN OTHERS THEN
            -- If conversion fails, return NULL
            RETURN NULL;
    END;
END;
$$ LANGUAGE plpgsql;

-- Convert feeds table numeric columns to DECIMAL(10,2) with rounding
ALTER TABLE feeds ALTER COLUMN fd_dm TYPE DECIMAL(10,2) USING round_numeric_value(fd_dm);
ALTER TABLE feeds ALTER COLUMN fd_ash TYPE DECIMAL(10,2) USING round_numeric_value(fd_ash);
ALTER TABLE feeds ALTER COLUMN fd_cp TYPE DECIMAL(10,2) USING round_numeric_value(fd_cp);
ALTER TABLE feeds ALTER COLUMN fd_ee TYPE DECIMAL(10,2) USING round_numeric_value(fd_ee);
ALTER TABLE feeds ALTER COLUMN fd_cf TYPE DECIMAL(10,2) USING round_numeric_value(fd_cf);
ALTER TABLE feeds ALTER COLUMN fd_nfe TYPE DECIMAL(10,2) USING round_numeric_value(fd_nfe);
ALTER TABLE feeds ALTER COLUMN fd_st TYPE DECIMAL(10,2) USING round_numeric_value(fd_st);
ALTER TABLE feeds ALTER COLUMN fd_ndf TYPE DECIMAL(10,2) USING round_numeric_value(fd_ndf);
ALTER TABLE feeds ALTER COLUMN fd_hemicellulose TYPE DECIMAL(10,2) USING round_numeric_value(fd_hemicellulose);
ALTER TABLE feeds ALTER COLUMN fd_adf TYPE DECIMAL(10,2) USING round_numeric_value(fd_adf);
ALTER TABLE feeds ALTER COLUMN fd_cellulose TYPE DECIMAL(10,2) USING round_numeric_value(fd_cellulose);
ALTER TABLE feeds ALTER COLUMN fd_lg TYPE DECIMAL(10,2) USING round_numeric_value(fd_lg);
ALTER TABLE feeds ALTER COLUMN fd_ndin TYPE DECIMAL(10,2) USING round_numeric_value(fd_ndin);
ALTER TABLE feeds ALTER COLUMN fd_adin TYPE DECIMAL(10,2) USING round_numeric_value(fd_adin);
ALTER TABLE feeds ALTER COLUMN fd_ca TYPE DECIMAL(10,2) USING round_numeric_value(fd_ca);
ALTER TABLE feeds ALTER COLUMN fd_p TYPE DECIMAL(10,2) USING round_numeric_value(fd_p);

-- Convert custom_feeds table numeric columns to DECIMAL(10,2) with rounding
ALTER TABLE custom_feeds ALTER COLUMN fd_dm TYPE DECIMAL(10,2) USING round_numeric_value(fd_dm);
ALTER TABLE custom_feeds ALTER COLUMN fd_ash TYPE DECIMAL(10,2) USING round_numeric_value(fd_ash);
ALTER TABLE custom_feeds ALTER COLUMN fd_cp TYPE DECIMAL(10,2) USING round_numeric_value(fd_cp);
ALTER TABLE custom_feeds ALTER COLUMN fd_ee TYPE DECIMAL(10,2) USING round_numeric_value(fd_ee);
ALTER TABLE custom_feeds ALTER COLUMN fd_cf TYPE DECIMAL(10,2) USING round_numeric_value(fd_cf);
ALTER TABLE custom_feeds ALTER COLUMN fd_nfe TYPE DECIMAL(10,2) USING round_numeric_value(fd_nfe);
ALTER TABLE custom_feeds ALTER COLUMN fd_st TYPE DECIMAL(10,2) USING round_numeric_value(fd_st);
ALTER TABLE custom_feeds ALTER COLUMN fd_ndf TYPE DECIMAL(10,2) USING round_numeric_value(fd_ndf);
ALTER TABLE custom_feeds ALTER COLUMN fd_hemicellulose TYPE DECIMAL(10,2) USING round_numeric_value(fd_hemicellulose);
ALTER TABLE custom_feeds ALTER COLUMN fd_adf TYPE DECIMAL(10,2) USING round_numeric_value(fd_adf);
ALTER TABLE custom_feeds ALTER COLUMN fd_cellulose TYPE DECIMAL(10,2) USING round_numeric_value(fd_cellulose);
ALTER TABLE custom_feeds ALTER COLUMN fd_lg TYPE DECIMAL(10,2) USING round_numeric_value(fd_lg);
ALTER TABLE custom_feeds ALTER COLUMN fd_ndin TYPE DECIMAL(10,2) USING round_numeric_value(fd_ndin);
ALTER TABLE custom_feeds ALTER COLUMN fd_adin TYPE DECIMAL(10,2) USING round_numeric_value(fd_adin);
ALTER TABLE custom_feeds ALTER COLUMN fd_ca TYPE DECIMAL(10,2) USING round_numeric_value(fd_ca);
ALTER TABLE custom_feeds ALTER COLUMN fd_p TYPE DECIMAL(10,2) USING round_numeric_value(fd_p);

-- Update comments to reflect the new precision control
COMMENT ON COLUMN feeds.fd_dm IS 'Dry matter percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_ash IS 'Ash percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_cp IS 'Crude protein percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_ee IS 'Ether extract percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_cf IS 'Crude fiber percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_nfe IS 'Nitrogen free extract percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_st IS 'Starch percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_ndf IS 'Neutral detergent fiber percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_hemicellulose IS 'Hemicellulose percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_adf IS 'Acid detergent fiber percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_cellulose IS 'Cellulose percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_lg IS 'Lignin percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_ndin IS 'Neutral detergent insoluble nitrogen percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_adin IS 'Acid detergent insoluble nitrogen percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_ca IS 'Calcium percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN feeds.fd_p IS 'Phosphorus percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';

COMMENT ON COLUMN custom_feeds.fd_dm IS 'Dry matter percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_ash IS 'Ash percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_cp IS 'Crude protein percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_ee IS 'Ether extract percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_cf IS 'Crude fiber percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_nfe IS 'Nitrogen free extract percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_st IS 'Starch percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_ndf IS 'Neutral detergent fiber percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_hemicellulose IS 'Hemicellulose percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_adf IS 'Acid detergent fiber percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_cellulose IS 'Cellulose percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_lg IS 'Lignin percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_ndin IS 'Neutral detergent insoluble nitrogen percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_adin IS 'Acid detergent insoluble nitrogen percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_ca IS 'Calcium percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';
COMMENT ON COLUMN custom_feeds.fd_p IS 'Phosphorus percentage stored as DECIMAL(10,2) - rounded to 2 decimal places';

-- Clean up the helper function
DROP FUNCTION round_numeric_value(TEXT);
