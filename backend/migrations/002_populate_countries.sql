-- Migration 002: Populate country Table with World Countries
-- Date: 2025-01-27
-- Description: Insert all world countries with ISO 3-letter codes into country table

-- =====================================================
-- POPULATE COUNTRY TABLE
-- =====================================================

INSERT INTO country (name, country_code) VALUES
-- A
('Afghanistan', 'AFG'),
('Albania', 'ALB'),
('Algeria', 'DZA'),
('Andorra', 'AND'),
('Angola', 'AGO'),
('Argentina', 'ARG'),
('Armenia', 'ARM'),
('Australia', 'AUS'),
('Austria', 'AUT'),
('Azerbaijan', 'AZE'),

-- B
('Bahamas', 'BHS'),
('Bahrain', 'BHR'),
('Bangladesh', 'BGD'),
('Barbados', 'BRB'),
('Belarus', 'BLR'),
('Belgium', 'BEL'),
('Belize', 'BLZ'),
('Benin', 'BEN'),
('Bhutan', 'BTN'),
('Bolivia', 'BOL'),
('Bosnia and Herzegovina', 'BIH'),
('Botswana', 'BWA'),
('Brazil', 'BRA'),
('Brunei', 'BRN'),
('Bulgaria', 'BGR'),
('Burkina Faso', 'BFA'),
('Burundi', 'BDI'),

-- C
('Cambodia', 'KHM'),
('Cameroon', 'CMR'),
('Canada', 'CAN'),
('Cape Verde', 'CPV'),
('Central African Republic', 'CAF'),
('Chad', 'TCD'),
('Chile', 'CHL'),
('China', 'CHN'),
('Colombia', 'COL'),
('Comoros', 'COM'),
('Congo', 'COG'),
('Costa Rica', 'CRI'),
('Croatia', 'HRV'),
('Cuba', 'CUB'),
('Cyprus', 'CYP'),
('Czech Republic', 'CZE'),

-- D
('Democratic Republic of the Congo', 'COD'),
('Denmark', 'DNK'),
('Djibouti', 'DJI'),
('Dominica', 'DMA'),
('Dominican Republic', 'DOM'),

-- E
('Ecuador', 'ECU'),
('Egypt', 'EGY'),
('El Salvador', 'SLV'),
('Equatorial Guinea', 'GNQ'),
('Eritrea', 'ERI'),
('Estonia', 'EST'),
('Eswatini', 'SWZ'),
('Ethiopia', 'ETH'),

-- F
('Fiji', 'FJI'),
('Finland', 'FIN'),
('France', 'FRA'),

-- G
('Gabon', 'GAB'),
('Gambia', 'GMB'),
('Georgia', 'GEO'),
('Germany', 'DEU'),
('Ghana', 'GHA'),
('Greece', 'GRC'),
('Grenada', 'GRD'),
('Guatemala', 'GTM'),
('Guinea', 'GIN'),
('Guinea-Bissau', 'GNB'),
('Guyana', 'GUY'),

-- H
('Haiti', 'HTI'),
('Honduras', 'HND'),
('Hungary', 'HUN'),

-- I
('Iceland', 'ISL'),
('India', 'IND'),
('Indonesia', 'IDN'),
('Iran', 'IRN'),
('Iraq', 'IRQ'),
('Ireland', 'IRL'),
('Israel', 'ISR'),
('Italy', 'ITA'),
('Ivory Coast', 'CIV'),

-- J
('Jamaica', 'JAM'),
('Japan', 'JPN'),
('Jordan', 'JOR'),

-- K
('Kazakhstan', 'KAZ'),
('Kenya', 'KEN'),
('Kiribati', 'KIR'),
('Kuwait', 'KWT'),
('Kyrgyzstan', 'KGZ'),

-- L
('Laos', 'LAO'),
('Latvia', 'LVA'),
('Lebanon', 'LBN'),
('Lesotho', 'LSO'),
('Liberia', 'LBR'),
('Libya', 'LBY'),
('Liechtenstein', 'LIE'),
('Lithuania', 'LTU'),
('Luxembourg', 'LUX'),

-- M
('Madagascar', 'MDG'),
('Malawi', 'MWI'),
('Malaysia', 'MYS'),
('Maldives', 'MDV'),
('Mali', 'MLI'),
('Malta', 'MLT'),
('Marshall Islands', 'MHL'),
('Mauritania', 'MRT'),
('Mauritius', 'MUS'),
('Mexico', 'MEX'),
('Micronesia', 'FSM'),
('Moldova', 'MDA'),
('Monaco', 'MCO'),
('Mongolia', 'MNG'),
('Montenegro', 'MNE'),
('Morocco', 'MAR'),
('Mozambique', 'MOZ'),
('Myanmar', 'MMR'),

-- N
('Namibia', 'NAM'),
('Nauru', 'NRU'),
('Nepal', 'NPL'),
('Netherlands', 'NLD'),
('New Zealand', 'NZL'),
('Nicaragua', 'NIC'),
('Niger', 'NER'),
('Nigeria', 'NGA'),
('North Korea', 'PRK'),
('North Macedonia', 'MKD'),
('Norway', 'NOR'),

-- O
('Oman', 'OMN'),

-- P
('Pakistan', 'PAK'),
('Palau', 'PLW'),
('Panama', 'PAN'),
('Papua New Guinea', 'PNG'),
('Paraguay', 'PRY'),
('Peru', 'PER'),
('Philippines', 'PHL'),
('Poland', 'POL'),
('Portugal', 'PRT'),

-- Q
('Qatar', 'QAT'),

-- R
('Romania', 'ROU'),
('Russia', 'RUS'),
('Rwanda', 'RWA'),

-- S
('Saint Kitts and Nevis', 'KNA'),
('Saint Lucia', 'LCA'),
('Saint Vincent and the Grenadines', 'VCT'),
('Samoa', 'WSM'),
('San Marino', 'SMR'),
('Sao Tome and Principe', 'STP'),
('Saudi Arabia', 'SAU'),
('Senegal', 'SEN'),
('Serbia', 'SRB'),
('Seychelles', 'SYC'),
('Sierra Leone', 'SLE'),
('Singapore', 'SGP'),
('Slovakia', 'SVK'),
('Slovenia', 'SVN'),
('Solomon Islands', 'SLB'),
('Somalia', 'SOM'),
('South Africa', 'ZAF'),
('South Korea', 'KOR'),
('South Sudan', 'SSD'),
('Spain', 'ESP'),
('Sri Lanka', 'LKA'),
('Sudan', 'SDN'),
('Suriname', 'SUR'),
('Sweden', 'SWE'),
('Switzerland', 'CHE'),
('Syria', 'SYR'),

-- T
('Taiwan', 'TWN'),
('Tajikistan', 'TJK'),
('Tanzania', 'TZA'),
('Thailand', 'THA'),
('Timor-Leste', 'TLS'),
('Togo', 'TGO'),
('Tonga', 'TON'),
('Trinidad and Tobago', 'TTO'),
('Tunisia', 'TUN'),
('Turkey', 'TUR'),
('Turkmenistan', 'TKM'),
('Tuvalu', 'TUV'),

-- U
('Uganda', 'UGA'),
('Ukraine', 'UKR'),
('United Arab Emirates', 'ARE'),
('United Kingdom', 'GBR'),
('United States', 'USA'),
('Uruguay', 'URY'),
('Uzbekistan', 'UZB'),

-- V
('Vanuatu', 'VUT'),
('Vatican City', 'VAT'),
('Venezuela', 'VEN'),
('Vietnam', 'VNM'),

-- Y
('Yemen', 'YEM'),

-- Z
('Zambia', 'ZMB'),
('Zimbabwe', 'ZWE')

ON CONFLICT (name) DO NOTHING;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Check total number of countries inserted
-- SELECT COUNT(*) as total_countries FROM country;

-- Verify some sample countries
-- SELECT name, country_code, created_at FROM country 
-- WHERE country_code IN ('USA', 'GBR', 'IND', 'ETH', 'BRA', 'AUS') 
-- ORDER BY name;

-- Check for any duplicate country codes or names
-- SELECT country_code, COUNT(*) FROM country GROUP BY country_code HAVING COUNT(*) > 1;
-- SELECT name, COUNT(*) FROM country GROUP BY name HAVING COUNT(*) > 1;

COMMIT; 