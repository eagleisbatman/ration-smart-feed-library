#!/usr/bin/env node

/**
 * Import Vietnamese Feeds from Old Database
 * Copies Vietnam feeds from old database to new database with regional variations support
 */

import pg from 'pg';
const { Client } = pg;
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Source database (production - old database)
const sourceClient = new Client({
  host: '18.60.203.199',
  port: 5432,
  user: 'feed_formulation_user',
  password: 'feed_formulation_password369',
  database: 'feed_formulation_db',
  connectionTimeoutMillis: 10000
});

// Target database (new - from Railway)
let targetConfig;

if (process.env.DATABASE_URL) {
  const url = new URL(process.env.DATABASE_URL);
  targetConfig = {
    host: url.hostname,
    port: parseInt(url.port || '5432'),
    user: url.username,
    password: url.password,
    database: url.pathname.slice(1),
  };
} else {
  targetConfig = {
    host: process.env.NEW_DB_HOST || 'localhost',
    port: parseInt(process.env.NEW_DB_PORT || '5432'),
    user: process.env.NEW_DB_USER || 'postgres',
    password: process.env.NEW_DB_PASSWORD || '',
    database: process.env.NEW_DB_NAME || 'railway',
  };
}

const targetClient = new Client({
  ...targetConfig,
  connectionTimeoutMillis: 10000
});

async function importVietnamFeeds() {
  try {
    console.log('🔌 Connecting to source database...');
    await sourceClient.connect();
    console.log('✅ Connected to source database\n');

    console.log('🔌 Connecting to target database...');
    await targetClient.connect();
    console.log('✅ Connected to target database\n');

    // Get Vietnam country ID from target
    const vietnamResult = await targetClient.query(`
      SELECT id, name, country_code 
      FROM countries 
      WHERE country_code = 'VNM' OR name ILIKE '%vietnam%'
      LIMIT 1;
    `);

    if (vietnamResult.rows.length === 0) {
      throw new Error('Vietnam not found in target database');
    }

    const vietnam = vietnamResult.rows[0];
    console.log(`✅ Found Vietnam: ${vietnam.name} (${vietnam.country_code})`);
    console.log(`   ID: ${vietnam.id}\n`);

    // Fetch all Vietnam feeds from source
    console.log('📥 Fetching Vietnam feeds from source database...');
    const sourceFeeds = await sourceClient.query(`
      SELECT 
        f.fd_name,
        f.fd_type,
        f.fd_category,
        f.fd_dm::text as fd_dm,
        f.fd_ash::text as fd_ash,
        f.fd_cp::text as fd_cp,
        f.fd_ee::text as fd_ee,
        f.fd_st::text as fd_st,
        f.fd_ndf::text as fd_ndf,
        f.fd_adf::text as fd_adf,
        f.fd_lg::text as fd_lg,
        f.fd_ca::text as fd_ca,
        f.fd_p::text as fd_p,
        f.fd_cf::text as fd_cf,
        f.fd_nfe::text as fd_nfe,
        f.fd_hemicellulose::text as fd_hemicellulose,
        f.fd_cellulose::text as fd_cellulose,
        f.fd_ndin::text as fd_ndin,
        f.fd_adin::text as fd_adin,
        f.fd_npn_cp::text as fd_npn_cp,
        f.fd_season,
        f.fd_orginin,
        f.fd_ipb_local_lab,
        f.fd_code
      FROM feeds f
      JOIN country c ON f.fd_country_id = c.id
      WHERE c.country_code = 'VNM' OR c.name ILIKE '%vietnam%'
      ORDER BY f.fd_name;
    `);

    console.log(`   Found ${sourceFeeds.rows.length} Vietnam feeds\n`);

    if (sourceFeeds.rows.length === 0) {
      console.log('⚠️  No Vietnam feeds found in source database');
      return;
    }

    // Group feeds by name+type+category
    console.log('📊 Grouping feeds by name...');
    const feedGroups = {};
    
    sourceFeeds.rows.forEach(feed => {
      const key = `${(feed.fd_name || '').toLowerCase()}_${feed.fd_type || ''}_${feed.fd_category || ''}`;
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
    console.log(`   Total variations: ${sourceFeeds.rows.length}\n`);

    // Helper functions to safely convert to number (ensures it's a JavaScript Number type)
    // PostgreSQL returns numeric fields as strings, so we need to convert them
    const safeNumber = (val) => {
      if (val === null || val === undefined || val === '') return null;
      // Handle both string and number types
      if (typeof val === 'string') {
        const trimmed = val.trim();
        if (trimmed === '' || trimmed === 'null' || trimmed === 'undefined') return null;
        const num = parseFloat(trimmed);
        return isNaN(num) ? null : num;
      }
      // Already a number
      const num = Number(val);
      return isNaN(num) ? null : num;
    };
    
    // Helper function to safely convert to integer (ensures it's a JavaScript Number type)
    const safeInteger = (val) => {
      if (val === null || val === undefined || val === '') return 0;
      // Handle both string and number types
      if (typeof val === 'string') {
        const trimmed = val.trim();
        if (trimmed === '' || trimmed === 'null' || trimmed === 'undefined') return 0;
        const num = parseFloat(trimmed);
        return isNaN(num) ? 0 : Math.round(num);
      }
      // Already a number
      const num = Number(val);
      return isNaN(num) ? 0 : Math.round(num);
    };

    // Import feeds
    console.log('📤 Importing feeds to target database...');
    let feedCount = 0;
    let variationCount = 0;
    let skipCount = 0;

    for (const [key, group] of Object.entries(feedGroups)) {
      let feedId = null; // Declare feedId in outer scope
      try {
        const baseFeed = group.baseFeed;
        
        // Check if base feed already exists
        const existingFeed = await targetClient.query(`
          SELECT id FROM feeds 
          WHERE fd_name_default = $1 
          AND fd_type = $2
          AND fd_category = $3
          AND fd_country_id = $4
          LIMIT 1;
        `, [
          String(baseFeed.fd_name || '').trim(),
          String(baseFeed.fd_type || '').trim(),
          String(baseFeed.fd_category || '').trim(),
          vietnam.id
        ]);

        if (existingFeed.rows.length > 0) {
          feedId = existingFeed.rows[0].id;
          // Feed exists, skip creating but still process variations
        } else {
          // Create base feed
          const feedCode = baseFeed.fd_code || `VNM-${String(feedCount + 1).padStart(4, '0')}`;
          
          const result = await targetClient.query(`
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
            String(baseFeed.fd_name || '').trim(),
            String(baseFeed.fd_type || '').trim(),
            String(baseFeed.fd_category || '').trim(),
            vietnam.id,
            safeNumber(baseFeed.fd_dm),
            safeNumber(baseFeed.fd_ash),
            safeNumber(baseFeed.fd_cp),
            safeNumber(baseFeed.fd_ee),
            safeNumber(baseFeed.fd_st),
            safeNumber(baseFeed.fd_ndf),
            safeNumber(baseFeed.fd_adf),
            safeNumber(baseFeed.fd_lg),
            safeNumber(baseFeed.fd_ca),
            safeNumber(baseFeed.fd_p),
            safeNumber(baseFeed.fd_cf),
            safeNumber(baseFeed.fd_nfe),
            safeNumber(baseFeed.fd_hemicellulose),
            safeNumber(baseFeed.fd_cellulose),
            safeNumber(baseFeed.fd_ndin),
            safeNumber(baseFeed.fd_adin),
            safeInteger(baseFeed.fd_npn_cp),
            baseFeed.fd_season ? String(baseFeed.fd_season).trim() : null,
            baseFeed.fd_orginin ? String(baseFeed.fd_orginin).trim() : null,
            baseFeed.fd_ipb_local_lab ? String(baseFeed.fd_ipb_local_lab).trim() : null
          ].map((val, idx) => {
            // Double-check numeric parameters (indices 5-21 are numeric, 22 is integer)
            if (idx >= 5 && idx <= 21 && val !== null && typeof val !== 'number') {
              return safeNumber(val);
            }
            if (idx === 22 && val !== null && typeof val !== 'number') {
              return safeInteger(val);
            }
            return val;
          }));
          
          feedId = result.rows[0].id;
          feedCount++;
          
          if (feedCount % 50 === 0) {
            console.log(`   ✅ Created ${feedCount} base feeds...`);
          }
        }

        // Insert all variations (including base feed as first variation)
        const allVariations = [baseFeed, ...group.variations];
        
        for (const variation of allVariations) {
          // Convert values before using in queries
          const varDm = safeNumber(variation.fd_dm);
          const varCp = safeNumber(variation.fd_cp);
          const varNdf = safeNumber(variation.fd_ndf);
          
          // Check if variation already exists (by nutritional values)
          const existingVar = await targetClient.query(`
            SELECT id FROM feed_regional_variations
            WHERE feed_id = $1
            AND (fd_dm IS NULL AND $2::numeric IS NULL OR fd_dm = $2::numeric)
            AND (fd_cp IS NULL AND $3::numeric IS NULL OR fd_cp = $3::numeric)
            AND (fd_ndf IS NULL AND $4::numeric IS NULL OR fd_ndf = $4::numeric)
            LIMIT 1;
          `, [
            feedId, 
            varDm, 
            varCp, 
            varNdf
          ]);

          if (existingVar.rows.length === 0) {
            // Convert ALL values to proper types BEFORE building params array
            // Ensure we have proper JavaScript Number types, not strings
            const params = [
              feedId,                                                    // $1 - UUID
              null,                                                      // $2 - region (VARCHAR)
              null,                                                      // $3 - zone (VARCHAR)
              null,                                                      // $4 - town_woreda (VARCHAR)
              null,                                                      // $5 - agro_ecology (VARCHAR)
              null,                                                      // $6 - production_system (VARCHAR)
              varDm,                                                     // $7 - fd_dm (NUMERIC)
              safeNumber(variation.fd_ash),                             // $8 - fd_ash (NUMERIC)
              varCp,                                                     // $9 - fd_cp (NUMERIC)
              safeNumber(variation.fd_ee),                              // $10 - fd_ee (NUMERIC)
              safeNumber(variation.fd_st),                              // $11 - fd_st (NUMERIC)
              varNdf,                                                    // $12 - fd_ndf (NUMERIC)
              safeNumber(variation.fd_adf),                             // $13 - fd_adf (NUMERIC)
              safeNumber(variation.fd_lg),                              // $14 - fd_lg (NUMERIC)
              safeNumber(variation.fd_ca),                              // $15 - fd_ca (NUMERIC)
              safeNumber(variation.fd_p),                               // $16 - fd_p (NUMERIC)
              safeNumber(variation.fd_cf),                              // $17 - fd_cf (NUMERIC)
              safeNumber(variation.fd_nfe),                            // $18 - fd_nfe (NUMERIC)
              safeNumber(variation.fd_hemicellulose),                  // $19 - fd_hemicellulose (NUMERIC)
              safeNumber(variation.fd_cellulose),                      // $20 - fd_cellulose (NUMERIC)
              safeNumber(variation.fd_ndin),                           // $21 - fd_ndin (NUMERIC)
              safeNumber(variation.fd_adin),                           // $22 - fd_adin (NUMERIC)
              safeInteger(variation.fd_npn_cp),                        // $23 - fd_npn_cp (INTEGER) - MUST BE INTEGER
              variation.fd_orginin ? String(variation.fd_orginin).trim() : null, // $24 - reference (VARCHAR)
              null,                                                     // $25 - processing_methods (VARCHAR)
              null                                                      // $26 - forms_of_feed_presentation (VARCHAR)
            ];
            
            // CRITICAL: Final type verification - ensure fd_npn_cp (index 22) is definitely an integer
            // PostgreSQL will reject if this is a float or string
            if (params[22] === null || params[22] === undefined) {
              params[22] = 0;
            } else {
              const npnValue = Number(params[22]);
              if (isNaN(npnValue)) {
                params[22] = 0;
              } else {
                params[22] = Math.round(npnValue);
              }
            }
            
            // Verify all numeric params are numbers (not strings)
            for (let i = 6; i <= 21; i++) { // Indices 6-21 are NUMERIC fields
              if (params[i] !== null && typeof params[i] !== 'number') {
                const num = Number(params[i]);
                params[i] = isNaN(num) ? null : num;
              }
            }
            
            try {
              await targetClient.query(`
                INSERT INTO feed_regional_variations (
                  feed_id, region, zone, town_woreda, agro_ecology, production_system,
                  fd_dm, fd_ash, fd_cp, fd_ee, fd_st, fd_ndf, fd_adf, fd_lg,
                  fd_ca, fd_p, fd_cf, fd_nfe, fd_hemicellulose, fd_cellulose,
                  fd_ndin, fd_adin, fd_npn_cp, reference, processing_methods, forms_of_feed_presentation,
                  created_at, updated_at
                ) VALUES (
                  $1, $2, $3, $4, $5, $6,
                  $7::numeric, $8::numeric, $9::numeric, $10::numeric, $11::numeric, $12::numeric, $13::numeric, $14::numeric,
                  $15::numeric, $16::numeric, $17::numeric, $18::numeric, $19::numeric, $20::numeric,
                  $21::numeric, $22::numeric, $23::integer, $24, $25, $26,
                  NOW(), NOW()
                )
              `, params);
              
              variationCount++;
            } catch (insertError) {
              // Log insertion errors but don't stop the process
              const insertErrorMsg = insertError instanceof Error ? insertError.message : String(insertError);
              if (!insertErrorMsg.includes('duplicate') && !insertErrorMsg.includes('already exists')) {
                console.log(`      ⚠️  Failed to insert variation for ${group.baseFeed.fd_name}: ${insertErrorMsg.substring(0, 100)}`);
              }
            }
          }
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        // Only log non-duplicate errors
        if (!errorMessage.includes('duplicate') && !errorMessage.includes('already exists')) {
          const feedName = group?.baseFeed?.fd_name || 'Unknown';
          console.log(`   ❌ Error importing ${feedName}: ${errorMessage}`);
          // Log detailed error for debugging
          if (errorMessage.includes('integer') && group?.baseFeed && skipCount < 5) {
            const bf = group.baseFeed;
            const npn = safeInteger(bf.fd_npn_cp);
            console.log(`      Debug: fd_npn_cp raw = ${bf.fd_npn_cp} (${typeof bf.fd_npn_cp}), converted = ${npn} (${typeof npn})`);
            console.log(`      Debug: fd_dm = ${safeNumber(bf.fd_dm)} (${typeof safeNumber(bf.fd_dm)}), fd_cp = ${safeNumber(bf.fd_cp)} (${typeof safeNumber(bf.fd_cp)})`);
            console.log(`      Debug: feedId exists = ${!!feedId}, variation count = ${group.variations.length}`);
          }
        }
        skipCount++;
      }
    }

    console.log(`\n✅ Import complete!`);
    console.log(`   ✅ Base feeds created: ${feedCount}`);
    console.log(`   ✅ Regional variations stored: ${variationCount}`);
    console.log(`   ⚠️  Skipped: ${skipCount}`);

    // Verify
    const feedCountResult = await targetClient.query(`
      SELECT COUNT(*) as count 
      FROM feeds 
      WHERE fd_country_id = $1;
    `, [vietnam.id]);

    const varCountResult = await targetClient.query(`
      SELECT COUNT(*) as count 
      FROM feed_regional_variations frv
      JOIN feeds f ON frv.feed_id = f.id
      WHERE f.fd_country_id = $1;
    `, [vietnam.id]);

    console.log(`\n🔍 Verification:`);
    console.log(`   📊 Vietnam base feeds: ${feedCountResult.rows[0].count}`);
    console.log(`   📍 Vietnam regional variations: ${varCountResult.rows[0].count}`);

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('\n❌ Error:', errorMessage);
    process.exit(1);
  } finally {
    await sourceClient.end();
    await targetClient.end();
    console.log('\n🔌 Database connections closed.');
  }
}

importVietnamFeeds();

