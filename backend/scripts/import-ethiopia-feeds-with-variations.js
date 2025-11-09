#!/usr/bin/env node

/**
 * Import Ethiopia Feeds with Regional Variations
 * Groups feeds by name and stores regional variations separately
 */

import XLSX from 'xlsx';
import pg from 'pg';
const { Client } = pg;
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const EXCEL_FILE = join(__dirname, '../../../Analysed chemical composition of feeds (highlighted for compound feeds, horticultural wastes and agroindustrial byproducts).xls');
// SECURITY: Never hardcode credentials - use environment variables only
const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  console.error('❌ ERROR: DATABASE_URL environment variable is required');
  process.exit(1);
}

const SHEET_TO_FEED_TYPE = {
  'Compound feed': 'Concentrate',
  'Crop residues': 'Forage',
  'Hay': 'Forage',
  'Improved forage': 'Forage',
  'Indigenous browse spp': 'Forage',
  'Natural pature': 'Forage',
  'Horticultural by-products': 'Forage',
  'Other agricultural by-products': 'Concentrate',
  'Agro-industrial by-products': 'Concentrate',
  'Grains and grain screenings': 'Concentrate'
};

function findFeedNameColumn(columns) {
  const namePatterns = [
    'common name',
    'Common name',
    'Common/Local name',
    'Vernacular/common name',
    'Vernacular name',
    'common'
  ];
  
  for (const pattern of namePatterns) {
    const col = columns.find(c => 
      c.toLowerCase().includes(pattern.toLowerCase())
    );
    if (col) return col;
  }
  
  return null;
}

function findColumn(columns, patterns) {
  for (const pattern of patterns) {
    const col = columns.find(c => 
      c.toLowerCase().includes(pattern.toLowerCase())
    );
    if (col) return col;
  }
  return null;
}

function transformRow(row, sheetName, rowIndex) {
  const columns = Object.keys(row);
  const nameCol = findFeedNameColumn(columns);
  
  let feedName = row[nameCol] || 
                 row['Scientific name'] || 
                 row['Vernacular name'] ||
                 `${sheetName} ${rowIndex + 1}`;
  
  feedName = String(feedName).trim();
  if (!feedName || feedName === 'null' || feedName === 'undefined') {
    feedName = `${sheetName} Feed ${rowIndex + 1}`;
  }
  
  const feedType = row['Category'] 
    ? (row['Category'].toLowerCase().includes('compound') || 
       row['Category'].toLowerCase().includes('concentrate') ||
       row['Category'].toLowerCase().includes('grain') ||
       row['Category'].toLowerCase().includes('industrial'))
      ? 'Concentrate' 
      : 'Forage'
    : SHEET_TO_FEED_TYPE[sheetName] || 'Forage';
  
  const category = row['Sub-category'] || 
                   row['Sub-category '] || 
                   sheetName || 
                   '';
  
  const getValue = (colPatterns) => {
    for (const pattern of colPatterns) {
      const col = columns.find(c => 
        c.toLowerCase().includes(pattern.toLowerCase())
      );
      if (col && row[col] !== null && row[col] !== undefined && row[col] !== '') {
        const val = parseFloat(row[col]);
        return isNaN(val) ? null : val;
      }
    }
    return null;
  };
  
  // Extract location info
  const regionCol = findColumn(columns, ['Region', 'region']);
  const zoneCol = findColumn(columns, ['Zone', 'zone', 'Zone/sub-city', 'Zone/Sub-city', 'Zone/City', 'zone/city', 'Zone/subcity']);
  const townCol = findColumn(columns, ['Town', 'Woreda', 'Town/Woreda', 'Woreda/town', 'Woreda/town', 'Town/Woreda']);
  
  return {
    fd_name_default: feedName,
    fd_type: feedType,
    fd_category: String(category).trim() || feedType,
    fd_dm: getValue(['DM(%)', 'DM']),
    fd_ash: getValue(['ASH(%)', 'ASH']),
    fd_cp: getValue(['CP(%)', 'CP (%)', 'CP']),
    fd_ndf: getValue(['NDF(%)', 'NDF']),
    fd_adf: getValue(['ADF(%)', 'ADF']),
    fd_lg: getValue(['ADL(%)', 'ADL']),
    fd_ee: null,
    fd_st: null,
    fd_cf: null,
    fd_nfe: null,
    fd_hemicellulose: null,
    fd_cellulose: null,
    fd_ndin: null,
    fd_adin: null,
    fd_ca: null,
    fd_p: null,
    fd_npn_cp: 0,
    fd_season: '',
    fd_orginin: row['Reference'] || '',
    fd_ipb_local_lab: '',
    // Regional info
    region: regionCol ? String(row[regionCol] || '').trim() : null,
    zone: zoneCol ? String(row[zoneCol] || '').trim() : null,
    town_woreda: townCol ? String(row[townCol] || '').trim() : null,
    agro_ecology: row['Agro-ecology'] || row['Agroecology'] || null,
    production_system: row['Production system'] || null,
    processing_methods: row['Procssing methods'] || row['Processing methods'] || null,
    forms_of_feed_presentation: row['Forms of feed presentation'] || null,
    reference: row['Reference'] || null
  };
}

async function importFeeds() {
  const client = new Client({
    connectionString: DATABASE_URL
  });

  try {
    console.log('🔌 Connecting to database...');
    await client.connect();
    console.log('✅ Connected!\n');

    // Get Ethiopia country ID
    const ethiopiaResult = await client.query(`
      SELECT id, name, country_code 
      FROM countries 
      WHERE country_code = 'ETH' OR name ILIKE '%ethiopia%'
      LIMIT 1;
    `);

    if (ethiopiaResult.rows.length === 0) {
      throw new Error('Ethiopia not found in database');
    }

    const ethiopia = ethiopiaResult.rows[0];
    console.log(`✅ Found Ethiopia: ${ethiopia.name} (${ethiopia.country_code})`);
    console.log(`   ID: ${ethiopia.id}\n`);

    // Get feed types
    const feedTypes = await client.query('SELECT id, type_name FROM feed_types');
    const feedTypeMap = {};
    feedTypes.rows.forEach(ft => {
      feedTypeMap[ft.type_name] = ft.id;
    });

    // Read Excel
    console.log('📖 Reading Excel file...');
    const workbook = XLSX.readFile(EXCEL_FILE);
    const allFeeds = [];

    workbook.SheetNames.forEach((sheetName) => {
      console.log(`\n📋 Processing sheet: "${sheetName}"`);
      const worksheet = workbook.Sheets[sheetName];
      const data = XLSX.utils.sheet_to_json(worksheet, { defval: null });
      
      console.log(`   Found ${data.length} rows`);
      
      data.forEach((row, index) => {
        try {
          const feedData = transformRow(row, sheetName, index);
          
          if (!feedData.fd_name_default || !feedData.fd_dm) {
            return; // Skip invalid rows
          }
          
          allFeeds.push(feedData);
        } catch (error) {
          // Skip errors
        }
      });
    });

    console.log(`\n✅ Total feeds prepared: ${allFeeds.length}`);

    // Group feeds by name+type+category
    console.log('\n📊 Grouping feeds by name...');
    const feedGroups = {};
    
    allFeeds.forEach(feed => {
      const key = `${feed.fd_name_default.toLowerCase()}_${feed.fd_type}_${feed.fd_category}`;
      if (!feedGroups[key]) {
        feedGroups[key] = {
          baseFeed: feed,
          variations: []
        };
      } else {
        feedGroups[key].variations.push(feed);
      }
    });

    console.log(`   Found ${Object.keys(feedGroups).length} unique feed names`);
    console.log(`   Total variations: ${allFeeds.length}`);

    // Import feeds
    console.log('\n📤 Importing feeds to database...');
    let feedCount = 0;
    let variationCount = 0;
    let skipCount = 0;

    for (const [key, group] of Object.entries(feedGroups)) {
      try {
        const baseFeed = group.baseFeed;
        
        // Check if base feed already exists
        const existingFeed = await client.query(`
          SELECT id FROM feeds 
          WHERE fd_name_default = $1 
          AND fd_type = $2
          AND fd_category = $3
          AND fd_country_id = $4
          LIMIT 1;
        `, [baseFeed.fd_name_default, baseFeed.fd_type, baseFeed.fd_category, ethiopia.id]);

        let feedId;
        
        if (existingFeed.rows.length > 0) {
          feedId = existingFeed.rows[0].id;
          skipCount++;
        } else {
          // Create base feed (use first variation's nutritional values as base)
          const feedCode = `ETH-${String(feedCount + 1).padStart(4, '0')}`;
          
          const result = await client.query(`
            INSERT INTO feeds (
              fd_code, fd_name_default, fd_type, fd_category, fd_country_id,
              fd_dm, fd_ash, fd_cp, fd_ee, fd_st, fd_ndf, fd_adf, fd_lg,
              fd_ca, fd_p, fd_cf, fd_nfe, fd_hemicellulose, fd_cellulose,
              fd_ndin, fd_adin, fd_npn_cp, fd_season, fd_orginin, fd_ipb_local_lab,
              is_active, created_at, updated_at
            ) VALUES (
              $1, $2, $3, $4, $5,
              $6, $7, $8, $9, $10, $11, $12, $13,
              $14, $15, $16, $17, $18, $19,
              $20, $21, $22, $23, $24, $25,
              true, NOW(), NOW()
            ) RETURNING id;
          `, [
            feedCode,
            baseFeed.fd_name_default,
            baseFeed.fd_type,
            baseFeed.fd_category,
            ethiopia.id,
            baseFeed.fd_dm,
            baseFeed.fd_ash,
            baseFeed.fd_cp,
            baseFeed.fd_ee,
            baseFeed.fd_st,
            baseFeed.fd_ndf,
            baseFeed.fd_adf,
            baseFeed.fd_lg,
            baseFeed.fd_ca,
            baseFeed.fd_p,
            baseFeed.fd_cf,
            baseFeed.fd_nfe,
            baseFeed.fd_hemicellulose,
            baseFeed.fd_cellulose,
            baseFeed.fd_ndin,
            baseFeed.fd_adin,
            baseFeed.fd_npn_cp,
            baseFeed.fd_season,
            baseFeed.fd_orginin,
            baseFeed.fd_ipb_local_lab
          ]);
          
          feedId = result.rows[0].id;
          feedCount++;
          
          if (feedCount % 50 === 0) {
            console.log(`   ✅ Created ${feedCount} base feeds...`);
          }
        }

        // Insert all variations (including base feed as first variation)
        const allVariations = [baseFeed, ...group.variations];
        
        for (const variation of allVariations) {
          // Check if variation already exists
          const existingVar = await client.query(`
            SELECT id FROM feed_regional_variations
            WHERE feed_id = $1
            AND COALESCE(region, '') = COALESCE($2, '')
            AND COALESCE(zone, '') = COALESCE($3, '')
            AND COALESCE(town_woreda, '') = COALESCE($4, '')
            LIMIT 1;
          `, [feedId, variation.region, variation.zone, variation.town_woreda]);

          if (existingVar.rows.length === 0) {
            await client.query(`
              INSERT INTO feed_regional_variations (
                feed_id, region, zone, town_woreda, agro_ecology, production_system,
                fd_dm, fd_ash, fd_cp, fd_ee, fd_st, fd_ndf, fd_adf, fd_lg,
                fd_ca, fd_p, fd_cf, fd_nfe, fd_hemicellulose, fd_cellulose,
                fd_ndin, fd_adin, fd_npn_cp, reference, processing_methods, forms_of_feed_presentation,
                created_at, updated_at
              ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11, $12, $13, $14,
                $15, $16, $17, $18, $19, $20,
                $21, $22, $23, $24, $25, $26,
                NOW(), NOW()
              )
            `, [
              feedId,
              variation.region,
              variation.zone,
              variation.town_woreda,
              variation.agro_ecology,
              variation.production_system,
              variation.fd_dm,
              variation.fd_ash,
              variation.fd_cp,
              variation.fd_ee,
              variation.fd_st,
              variation.fd_ndf,
              variation.fd_adf,
              variation.fd_lg,
              variation.fd_ca,
              variation.fd_p,
              variation.fd_cf,
              variation.fd_nfe,
              variation.fd_hemicellulose,
              variation.fd_cellulose,
              variation.fd_ndin,
              variation.fd_adin,
              variation.fd_npn_cp,
              variation.reference,
              variation.processing_methods,
              variation.forms_of_feed_presentation
            ]);
            
            variationCount++;
          }
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (!errorMessage.includes('duplicate') && !errorMessage.includes('already exists')) {
          console.log(`   ❌ Error importing ${group.baseFeed.fd_name_default}: ${errorMessage}`);
        }
        skipCount++;
      }
    }

    console.log(`\n✅ Import complete!`);
    console.log(`   ✅ Base feeds created: ${feedCount}`);
    console.log(`   ✅ Regional variations stored: ${variationCount}`);
    console.log(`   ⚠️  Skipped: ${skipCount}`);

    // Verify
    const feedCountResult = await client.query(`
      SELECT COUNT(*) as count 
      FROM feeds 
      WHERE fd_country_id = $1;
    `, [ethiopia.id]);

    const varCountResult = await client.query(`
      SELECT COUNT(*) as count 
      FROM feed_regional_variations frv
      JOIN feeds f ON frv.feed_id = f.id
      WHERE f.fd_country_id = $1;
    `, [ethiopia.id]);

    console.log(`\n🔍 Verification:`);
    console.log(`   📊 Base feeds: ${feedCountResult.rows[0].count}`);
    console.log(`   📍 Regional variations: ${varCountResult.rows[0].count}`);

    // Show sample
    const sample = await client.query(`
      SELECT 
        f.fd_name_default,
        f.fd_type,
        COUNT(frv.id) as variation_count
      FROM feeds f
      LEFT JOIN feed_regional_variations frv ON f.id = frv.feed_id
      WHERE f.fd_country_id = $1
      GROUP BY f.id, f.fd_name_default, f.fd_type
      ORDER BY variation_count DESC
      LIMIT 5;
    `, [ethiopia.id]);

    console.log(`\n📋 Sample feeds with variations:`);
    sample.rows.forEach((f, i) => {
      console.log(`   ${i+1}. ${f.fd_name_default} (${f.fd_type}) - ${f.variation_count} regional variations`);
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('\n❌ Error:', errorMessage);
    process.exit(1);
  } finally {
    await client.end();
    console.log('\n🔌 Database connection closed.');
  }
}

importFeeds();

