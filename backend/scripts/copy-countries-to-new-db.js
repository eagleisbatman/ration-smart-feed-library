#!/usr/bin/env node

/**
 * Copy Countries from Existing Database to New Database
 * Connects to both databases and copies all countries
 */

import pg from 'pg';
const { Client } = pg;

// Source database (existing)
const sourceClient = new Client({
  host: '18.60.203.199',
  port: 5432,
  user: 'feed_formulation_user',
  password: 'feed_formulation_password369',
  database: 'feed_formulation_db',
  connectionTimeoutMillis: 10000
});

// Target database (new - from Railway)
// Parse DATABASE_URL if provided, otherwise use individual env vars
let targetConfig;

if (process.env.DATABASE_URL) {
  // Parse DATABASE_URL: postgresql://user:password@host:port/database
  const url = new URL(process.env.DATABASE_URL);
  targetConfig = {
    host: url.hostname,
    port: parseInt(url.port || '5432'),
    user: url.username,
    password: url.password,
    database: url.pathname.slice(1), // Remove leading '/'
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

async function copyCountries() {
  try {
    console.log('🔌 Connecting to source database...');
    await sourceClient.connect();
    console.log('✅ Connected to source database\n');

    console.log('🔌 Connecting to target database...');
    await targetClient.connect();
    console.log('✅ Connected to target database\n');

    // Fetch all countries from source
    console.log('📥 Fetching countries from source database...');
    const sourceCountries = await sourceClient.query(`
      SELECT 
        id,
        name,
        country_code,
        currency,
        is_active,
        created_at,
        updated_at
      FROM country
      ORDER BY name;
    `);

    console.log(`   Found ${sourceCountries.rows.length} countries\n`);

    // Insert into target database
    console.log('📤 Copying countries to target database...');
    let successCount = 0;
    let skipCount = 0;

    for (const country of sourceCountries.rows) {
      try {
        await targetClient.query(`
          INSERT INTO countries (
            id,
            name,
            country_code,
            currency,
            is_active,
            created_at,
            updated_at,
            supported_languages
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
          ON CONFLICT (country_code) DO UPDATE SET
            name = EXCLUDED.name,
            currency = EXCLUDED.currency,
            is_active = EXCLUDED.is_active,
            updated_at = EXCLUDED.updated_at;
        `, [
          country.id,
          country.name,
          country.country_code,
          country.currency || null,
          country.is_active || false,
          country.created_at || new Date(),
          country.updated_at || new Date(),
          JSON.stringify(['en']) // Default to English, can be updated later
        ]);
        successCount++;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.log(`   ⚠️  Skipped ${country.name}: ${errorMessage}`);
        skipCount++;
      }
    }

    console.log(`\n✅ Copy complete!`);
    console.log(`   ✅ Successfully copied: ${successCount}`);
    console.log(`   ⚠️  Skipped: ${skipCount}`);

    // Verify copy
    console.log('\n🔍 Verifying copy...');
    const targetCount = await targetClient.query('SELECT COUNT(*) as count FROM countries');
    console.log(`   Target database has ${targetCount.rows[0].count} countries`);

    // Show sample countries
    const sampleCountries = await targetClient.query(`
      SELECT name, country_code, currency, is_active 
      FROM countries 
      ORDER BY name 
      LIMIT 10;
    `);
    
    console.log('\n📋 Sample countries in target database:');
    sampleCountries.rows.forEach(c => {
      console.log(`   - ${c.name} (${c.country_code}) - ${c.currency || 'N/A'} - ${c.is_active ? 'Active' : 'Inactive'}`);
    });

    // Set up default languages for countries
    console.log('\n🌐 Setting up default languages...');
    
    // Ethiopia: Afan Oromo, Amharic, English
    const ethiopia = await targetClient.query(`SELECT id FROM countries WHERE country_code = 'ETH'`);
    if (ethiopia.rows.length > 0) {
      await targetClient.query(`
        INSERT INTO country_languages (country_id, language_code, language_name, is_default, is_active)
        VALUES
          ($1, 'en', 'English', true, true),
          ($1, 'om', 'Afan Oromo', false, true),
          ($1, 'am', 'Amharic', false, true)
        ON CONFLICT (country_id, language_code) DO NOTHING;
      `, [ethiopia.rows[0].id]);
      
      await targetClient.query(`
        UPDATE countries 
        SET supported_languages = '["en", "om", "am"]'::jsonb
        WHERE country_code = 'ETH';
      `);
      console.log('   ✅ Ethiopia: English, Afan Oromo, Amharic');
    }

    // Vietnam: Vietnamese, English
    const vietnam = await targetClient.query(`SELECT id FROM countries WHERE country_code = 'VNM'`);
    if (vietnam.rows.length > 0) {
      await targetClient.query(`
        INSERT INTO country_languages (country_id, language_code, language_name, is_default, is_active)
        VALUES
          ($1, 'en', 'English', true, true),
          ($1, 'vi', 'Vietnamese', false, true)
        ON CONFLICT (country_id, language_code) DO NOTHING;
      `, [vietnam.rows[0].id]);
      
      await targetClient.query(`
        UPDATE countries 
        SET supported_languages = '["en", "vi"]'::jsonb
        WHERE country_code = 'VNM';
      `);
      console.log('   ✅ Vietnam: English, Vietnamese');
    }

    // Set English as default for all other countries
    const otherCountries = await targetClient.query(`
      SELECT id FROM countries 
      WHERE country_code NOT IN ('ETH', 'VNM')
      AND NOT EXISTS (
        SELECT 1 FROM country_languages WHERE country_id = countries.id
      )
    `);
    
    for (const country of otherCountries.rows) {
      await targetClient.query(`
        INSERT INTO country_languages (country_id, language_code, language_name, is_default, is_active)
        VALUES ($1, 'en', 'English', true, true)
        ON CONFLICT (country_id, language_code) DO NOTHING;
      `, [country.id]);
    }
    
    console.log(`   ✅ Set English as default for ${otherCountries.rows.length} other countries`);

    console.log('\n✅ Country copy and language setup complete!');

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('\n❌ Error:', errorMessage);
    const errorCode = error?.code;
    if (errorCode === 'ETIMEDOUT' || errorCode === 'EHOSTUNREACH' || errorCode === 'ECONNREFUSED') {
      console.error('   Database connection failed. Check credentials and network.');
    } else if (errorCode === '28P01') {
      console.error('   Authentication failed. Check username and password.');
    } else if (errorCode === '3D000') {
      console.error('   Database does not exist.');
    }
    process.exit(1);
  } finally {
    await sourceClient.end();
    await targetClient.end();
    console.log('\n🔌 Database connections closed.');
  }
}

copyCountries();

