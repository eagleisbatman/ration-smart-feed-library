-- Migration 006: Add currency column to country table and country_id foreign key to feeds table
-- Created: 2025-06-26
-- Description: Phase 1 of country-feed normalization - adds currency to country table and country_id FK to feeds table

-- ===========================
-- PHASE 1: ADD NEW COLUMNS
-- ===========================

-- 1. Add currency column to country table
ALTER TABLE country 
ADD COLUMN currency VARCHAR(10) DEFAULT NULL;

-- Add comment for the new column
COMMENT ON COLUMN country.currency IS 'Currency code for the country (e.g., USD, EUR, INR)';

-- 2. Add country_id foreign key column to feeds table
ALTER TABLE feeds 
ADD COLUMN country_id UUID DEFAULT NULL;

-- Add comment for the new column
COMMENT ON COLUMN feeds.country_id IS 'Foreign key reference to country table';

-- 3. Add foreign key constraint
ALTER TABLE feeds 
ADD CONSTRAINT fk_feeds_country_id 
FOREIGN KEY (country_id) REFERENCES country(id) ON DELETE SET NULL;

-- 4. Add index for performance
CREATE INDEX idx_feeds_country_id ON feeds(country_id);

-- ===========================
-- UPDATE CURRENCY DATA
-- ===========================

-- Update currency for existing countries (common currencies)
UPDATE country SET currency = 'USD' WHERE country_code IN ('USA', 'USD');
UPDATE country SET currency = 'EUR' WHERE country_code IN ('DEU', 'FRA', 'ITA', 'ESP', 'NLD', 'BEL', 'AUT', 'FIN', 'IRL', 'PRT', 'GRC', 'LUX', 'SVN', 'SVK', 'EST', 'LVA', 'LTU', 'CYP', 'MLT');
UPDATE country SET currency = 'GBP' WHERE country_code = 'GBR';
UPDATE country SET currency = 'INR' WHERE country_code = 'IND';
UPDATE country SET currency = 'CAD' WHERE country_code = 'CAN';
UPDATE country SET currency = 'AUD' WHERE country_code = 'AUS';
UPDATE country SET currency = 'JPY' WHERE country_code = 'JPN';
UPDATE country SET currency = 'CNY' WHERE country_code = 'CHN';
UPDATE country SET currency = 'BRL' WHERE country_code = 'BRA';
UPDATE country SET currency = 'RUB' WHERE country_code = 'RUS';
UPDATE country SET currency = 'ZAR' WHERE country_code = 'ZAF';
UPDATE country SET currency = 'MXN' WHERE country_code = 'MEX';
UPDATE country SET currency = 'KRW' WHERE country_code = 'KOR';
UPDATE country SET currency = 'SGD' WHERE country_code = 'SGP';
UPDATE country SET currency = 'CHF' WHERE country_code = 'CHE';
UPDATE country SET currency = 'NOK' WHERE country_code = 'NOR';
UPDATE country SET currency = 'SEK' WHERE country_code = 'SWE';
UPDATE country SET currency = 'DKK' WHERE country_code = 'DNK';
UPDATE country SET currency = 'PLN' WHERE country_code = 'POL';
UPDATE country SET currency = 'CZK' WHERE country_code = 'CZE';
UPDATE country SET currency = 'HUF' WHERE country_code = 'HUN';
UPDATE country SET currency = 'TRY' WHERE country_code = 'TUR';
UPDATE country SET currency = 'SAR' WHERE country_code = 'SAU';
UPDATE country SET currency = 'AED' WHERE country_code = 'ARE';
UPDATE country SET currency = 'THB' WHERE country_code = 'THA';
UPDATE country SET currency = 'MYR' WHERE country_code = 'MYS';
UPDATE country SET currency = 'IDR' WHERE country_code = 'IDN';
UPDATE country SET currency = 'PHP' WHERE country_code = 'PHL';
UPDATE country SET currency = 'VND' WHERE country_code = 'VNM';
UPDATE country SET currency = 'EGP' WHERE country_code = 'EGY';
UPDATE country SET currency = 'NGN' WHERE country_code = 'NGA';
UPDATE country SET currency = 'KES' WHERE country_code = 'KEN';
UPDATE country SET currency = 'GHS' WHERE country_code = 'GHA';
UPDATE country SET currency = 'ETB' WHERE country_code = 'ETH';
UPDATE country SET currency = 'UGX' WHERE country_code = 'UGA';
UPDATE country SET currency = 'TZS' WHERE country_code = 'TZA';
UPDATE country SET currency = 'RWF' WHERE country_code = 'RWA';
UPDATE country SET currency = 'ZMW' WHERE country_code = 'ZMB';
UPDATE country SET currency = 'BWP' WHERE country_code = 'BWA';
UPDATE country SET currency = 'NAD' WHERE country_code = 'NAM';
UPDATE country SET currency = 'SZL' WHERE country_code = 'SWZ';
UPDATE country SET currency = 'LSL' WHERE country_code = 'LSO';
UPDATE country SET currency = 'MWK' WHERE country_code = 'MWI';
UPDATE country SET currency = 'MZN' WHERE country_code = 'MOZ';
UPDATE country SET currency = 'AOA' WHERE country_code = 'AGO';

-- Set default USD for countries without specific currency mapping
UPDATE country SET currency = 'USD' WHERE currency IS NULL;

-- ===========================
-- VERIFICATION QUERIES
-- ===========================

-- These are for verification purposes (commented out for production)
-- SELECT 'Country table with currency' as description, count(*) as total_countries, count(currency) as countries_with_currency FROM country;
-- SELECT 'Feeds table with country_id' as description, count(*) as total_feeds, count(country_id) as feeds_with_country_id FROM feeds;
-- SELECT 'Sample countries with currency' as description, name, country_code, currency FROM country LIMIT 10; 