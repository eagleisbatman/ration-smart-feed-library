-- Migration: Align custom_feeds table columns with feeds table
-- Date: 2025-08-09
-- Description: Make custom_feeds table columns consistent with feeds table

-- Rename columns in custom_feeds to match feeds table
ALTER TABLE custom_feeds RENAME COLUMN fd_starch TO fd_st;
ALTER TABLE custom_feeds RENAME COLUMN fd_lignin TO fd_lg;
ALTER TABLE custom_feeds RENAME COLUMN fd_calcium TO fd_ca;
ALTER TABLE custom_feeds RENAME COLUMN fd_phosphorus TO fd_p;

-- Add missing columns to custom_feeds
ALTER TABLE custom_feeds ADD COLUMN fd_npn_cp INTEGER;
ALTER TABLE custom_feeds ADD COLUMN fd_country TEXT;
ALTER TABLE custom_feeds ADD COLUMN fd_season TEXT;

-- Convert data types to match feeds table
ALTER TABLE custom_feeds ALTER COLUMN fd_dm TYPE DOUBLE PRECISION USING CAST(fd_dm AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_ash TYPE DOUBLE PRECISION USING CAST(fd_ash AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_cp TYPE DOUBLE PRECISION USING CAST(fd_cp AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_ee TYPE DOUBLE PRECISION USING CAST(fd_ee AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_cf TYPE DOUBLE PRECISION USING CAST(fd_cf AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_nfe TYPE DOUBLE PRECISION USING CAST(fd_nfe AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_st TYPE DOUBLE PRECISION USING CAST(fd_st AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_ndf TYPE DOUBLE PRECISION USING CAST(fd_ndf AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_hemicellulose TYPE DOUBLE PRECISION USING CAST(fd_hemicellulose AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_adf TYPE DOUBLE PRECISION USING CAST(fd_adf AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_cellulose TYPE DOUBLE PRECISION USING CAST(fd_cellulose AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_lg TYPE DOUBLE PRECISION USING CAST(fd_lg AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_ndin TYPE DOUBLE PRECISION USING CAST(fd_ndin AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_adin TYPE DOUBLE PRECISION USING CAST(fd_adin AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_ca TYPE DOUBLE PRECISION USING CAST(fd_ca AS DOUBLE PRECISION);
ALTER TABLE custom_feeds ALTER COLUMN fd_p TYPE DOUBLE PRECISION USING CAST(fd_p AS DOUBLE PRECISION);

-- Convert fd_code to TEXT to match feeds table (after casting to double precision)
ALTER TABLE custom_feeds ALTER COLUMN fd_code TYPE TEXT;
