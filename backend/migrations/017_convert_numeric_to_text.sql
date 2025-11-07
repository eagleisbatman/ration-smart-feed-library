-- Migration 017: Convert all numeric columns to TEXT for data integrity
-- This migration converts all numeric columns in feeds and custom_feeds tables to TEXT
-- to prevent data type conflicts and improve data integrity

-- Convert feeds table numeric columns to TEXT
ALTER TABLE feeds ALTER COLUMN fd_code TYPE TEXT USING CAST(fd_code AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_dm TYPE TEXT USING CAST(fd_dm AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_ash TYPE TEXT USING CAST(fd_ash AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_cp TYPE TEXT USING CAST(fd_cp AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_ee TYPE TEXT USING CAST(fd_ee AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_cf TYPE TEXT USING CAST(fd_cf AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_nfe TYPE TEXT USING CAST(fd_nfe AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_st TYPE TEXT USING CAST(fd_st AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_ndf TYPE TEXT USING CAST(fd_ndf AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_hemicellulose TYPE TEXT USING CAST(fd_hemicellulose AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_adf TYPE TEXT USING CAST(fd_adf AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_cellulose TYPE TEXT USING CAST(fd_cellulose AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_lg TYPE TEXT USING CAST(fd_lg AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_ndin TYPE TEXT USING CAST(fd_ndin AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_adin TYPE TEXT USING CAST(fd_adin AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_ca TYPE TEXT USING CAST(fd_ca AS TEXT);
ALTER TABLE feeds ALTER COLUMN fd_p TYPE TEXT USING CAST(fd_p AS TEXT);

-- Convert custom_feeds table numeric columns to TEXT
ALTER TABLE custom_feeds ALTER COLUMN fd_dm TYPE TEXT USING CAST(fd_dm AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_ash TYPE TEXT USING CAST(fd_ash AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_cp TYPE TEXT USING CAST(fd_cp AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_ee TYPE TEXT USING CAST(fd_ee AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_cf TYPE TEXT USING CAST(fd_cf AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_nfe TYPE TEXT USING CAST(fd_nfe AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_starch TYPE TEXT USING CAST(fd_starch AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_ndf TYPE TEXT USING CAST(fd_ndf AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_hemicellulose TYPE TEXT USING CAST(fd_hemicellulose AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_adf TYPE TEXT USING CAST(fd_adf AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_cellulose TYPE TEXT USING CAST(fd_cellulose AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_lignin TYPE TEXT USING CAST(fd_lignin AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_ndin TYPE TEXT USING CAST(fd_ndin AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_adin TYPE TEXT USING CAST(fd_adin AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_calcium TYPE TEXT USING CAST(fd_calcium AS TEXT);
ALTER TABLE custom_feeds ALTER COLUMN fd_phosphorus TYPE TEXT USING CAST(fd_phosphorus AS TEXT);

-- Add comments to document the change
COMMENT ON COLUMN feeds.fd_code IS 'Feed code stored as TEXT for data integrity';
COMMENT ON COLUMN feeds.fd_dm IS 'Dry matter percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_ash IS 'Ash percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_cp IS 'Crude protein percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_ee IS 'Ether extract percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_cf IS 'Crude fiber percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_nfe IS 'Nitrogen free extract percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_st IS 'Starch percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_ndf IS 'Neutral detergent fiber percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_hemicellulose IS 'Hemicellulose percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_adf IS 'Acid detergent fiber percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_cellulose IS 'Cellulose percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_lg IS 'Lignin percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_ndin IS 'Neutral detergent insoluble nitrogen percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_adin IS 'Acid detergent insoluble nitrogen percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_ca IS 'Calcium percentage stored as TEXT';
COMMENT ON COLUMN feeds.fd_p IS 'Phosphorus percentage stored as TEXT';

COMMENT ON COLUMN custom_feeds.fd_dm IS 'Dry matter percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_ash IS 'Ash percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_cp IS 'Crude protein percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_ee IS 'Ether extract percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_cf IS 'Crude fiber percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_nfe IS 'Nitrogen free extract percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_starch IS 'Starch percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_ndf IS 'Neutral detergent fiber percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_hemicellulose IS 'Hemicellulose percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_adf IS 'Acid detergent fiber percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_cellulose IS 'Cellulose percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_lignin IS 'Lignin percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_ndin IS 'Neutral detergent insoluble nitrogen percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_adin IS 'Acid detergent insoluble nitrogen percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_calcium IS 'Calcium percentage stored as TEXT';
COMMENT ON COLUMN custom_feeds.fd_phosphorus IS 'Phosphorus percentage stored as TEXT';
