#!/usr/bin/env node

/**
 * Direct Database Import for Ethiopia Feeds
 * Imports feeds directly to PostgreSQL database (bypasses API)
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

// Map sheet names to feed types
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
    fd_ipb_local_lab: ''
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

    // Import to database
    console.log('\n📤 Importing feeds to database...');
    let successCount = 0;
    let skipCount = 0;

    for (const feed of allFeeds) {
      try {
        // Generate feed code (include row index to make unique)
        const feedCode = `ETH-${String(successCount + 1).padStart(4, '0')}`;

        // Get feed type ID
        const feedTypeId = feedTypeMap[feed.fd_type];
        if (!feedTypeId) {
          console.log(`   ⚠️  Skipping ${feed.fd_name_default}: Feed type "${feed.fd_type}" not found`);
          skipCount++;
          continue;
        }

        // Check if exact feed already exists (same name + type + category + all nutritional values)
        // This allows feeds with same name but different nutritional values (from different regions)
        const existing = await client.query(`
          SELECT id FROM feeds 
          WHERE fd_name_default = $1 
          AND fd_type = $2
          AND fd_category = $3
          AND fd_country_id = $4
          AND COALESCE(fd_dm, 0) = COALESCE($5, 0)
          AND COALESCE(fd_cp, 0) = COALESCE($6, 0)
          AND COALESCE(fd_ndf, 0) = COALESCE($7, 0)
          LIMIT 1;
        `, [
          feed.fd_name_default, 
          feed.fd_type, 
          feed.fd_category, 
          ethiopia.id,
          feed.fd_dm,
          feed.fd_cp,
          feed.fd_ndf
        ]);

        if (existing.rows.length > 0) {
          skipCount++;
          continue;
        }

        // Insert feed
        await client.query(`
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
          )
        `, [
          feedCode,
          feed.fd_name_default,
          feed.fd_type,
          feed.fd_category,
          ethiopia.id,
          feed.fd_dm,
          feed.fd_ash,
          feed.fd_cp,
          feed.fd_ee,
          feed.fd_st,
          feed.fd_ndf,
          feed.fd_adf,
          feed.fd_lg,
          feed.fd_ca,
          feed.fd_p,
          feed.fd_cf,
          feed.fd_nfe,
          feed.fd_hemicellulose,
          feed.fd_cellulose,
          feed.fd_ndin,
          feed.fd_adin,
          feed.fd_npn_cp,
          feed.fd_season,
          feed.fd_orginin,
          feed.fd_ipb_local_lab
        ]);

        successCount++;
        if (successCount % 50 === 0) {
          console.log(`   ✅ Imported ${successCount} feeds...`);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (!errorMessage.includes('duplicate') && !errorMessage.includes('already exists')) {
          console.log(`   ❌ Error importing ${feed.fd_name_default}: ${errorMessage}`);
        }
        skipCount++;
      }
    }

    console.log(`\n✅ Import complete!`);
    console.log(`   ✅ Successfully imported: ${successCount}`);
    console.log(`   ⚠️  Skipped: ${skipCount}`);

    // Verify
    const countResult = await client.query(`
      SELECT COUNT(*) as count 
      FROM feeds 
      WHERE fd_country_id = $1;
    `, [ethiopia.id]);

    console.log(`\n🔍 Verification: ${countResult.rows[0].count} feeds in database for Ethiopia`);

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

