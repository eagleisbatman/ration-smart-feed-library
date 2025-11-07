#!/usr/bin/env node

/**
 * Database Review Script for Feed Formulation
 * Connects to the existing database and reviews its structure
 */

import pg from 'pg';
const { Client } = pg;

const client = new Client({
  host: '18.60.203.199',
  port: 5432,
  user: 'feed_formulation_user',
  password: 'feed_formulation_password369',
  database: 'feed_formulation_db',
  connectionTimeoutMillis: 10000
});

async function reviewDatabase() {
  try {
    console.log('🔌 Connecting to database...');
    console.log(`   Host: ${client.host}:${client.port}`);
    console.log(`   Database: ${client.database}`);
    console.log(`   User: ${client.user}\n`);

    await client.connect();
    console.log('✅ Connected successfully!\n');

    // 1. List all tables
    console.log('📊 Database Tables:');
    console.log('='.repeat(60));
    const tables = await client.query(`
      SELECT 
        table_name,
        table_type
      FROM information_schema.tables
      WHERE table_schema = 'public'
      ORDER BY table_name;
    `);
    
    if (tables.rows.length > 0) {
      tables.rows.forEach((row, index) => {
        console.log(`${index + 1}. ${row.table_name} (${row.table_type})`);
      });
    } else {
      console.log('   No tables found.');
    }
    console.log('');

    // 2. Get detailed schema for each table
    console.log('📋 Table Schemas:');
    console.log('='.repeat(60));
    
    for (const table of tables.rows) {
      const tableName = table.table_name;
      console.log(`\n📌 Table: ${tableName}`);
      console.log('-'.repeat(60));
      
      const columns = await client.query(`
        SELECT 
          column_name,
          data_type,
          character_maximum_length,
          is_nullable,
          column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' 
          AND table_name = $1
        ORDER BY ordinal_position;
      `, [tableName]);

      if (columns.rows.length > 0) {
        console.log('Columns:');
        columns.rows.forEach(col => {
          const length = col.character_maximum_length 
            ? `(${col.character_maximum_length})` 
            : '';
          const nullable = col.is_nullable === 'YES' ? 'NULL' : 'NOT NULL';
          const defaultVal = col.column_default ? ` DEFAULT ${col.column_default}` : '';
          console.log(`  - ${col.column_name}: ${col.data_type}${length} ${nullable}${defaultVal}`);
        });
      }

      // Get foreign keys
      const foreignKeys = await client.query(`
        SELECT
          tc.constraint_name,
          kcu.column_name,
          ccu.table_name AS foreign_table_name,
          ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = $1;
      `, [tableName]);

      if (foreignKeys.rows.length > 0) {
        console.log('\nForeign Keys:');
        foreignKeys.rows.forEach(fk => {
          console.log(`  - ${fk.column_name} → ${fk.foreign_table_name}.${fk.foreign_column_name}`);
        });
      }

      // Get indexes
      const indexes = await client.query(`
        SELECT
          indexname,
          indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = $1;
      `, [tableName]);

      if (indexes.rows.length > 0) {
        console.log('\nIndexes:');
        indexes.rows.forEach(idx => {
          console.log(`  - ${idx.indexname}`);
        });
      }
    }

    // 3. Get row counts for each table
    console.log('\n\n📊 Table Row Counts:');
    console.log('='.repeat(60));
    for (const table of tables.rows) {
      const tableName = table.table_name;
      try {
        const count = await client.query(`SELECT COUNT(*) as count FROM ${tableName}`);
        console.log(`${tableName}: ${count.rows[0].count} rows`);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.log(`${tableName}: Error counting rows - ${errorMessage}`);
      }
    }

    // 4. Check for specific tables we're interested in
    console.log('\n\n🔍 Key Tables Analysis:');
    console.log('='.repeat(60));

    // Countries
    const countriesCheck = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'country'
      );
    `);
    if (countriesCheck.rows[0].exists) {
      const countries = await client.query('SELECT COUNT(*) as count FROM country');
      const activeCountries = await client.query('SELECT COUNT(*) as count FROM country WHERE is_active = true');
      console.log(`\n✅ Countries table exists: ${countries.rows[0].count} total, ${activeCountries.rows[0].count} active`);
      
      const countryList = await client.query('SELECT name, country_code, currency, is_active FROM country ORDER BY name LIMIT 10');
      if (countryList.rows.length > 0) {
        console.log('   Sample countries:');
        countryList.rows.forEach(c => {
          console.log(`     - ${c.name} (${c.country_code}) - ${c.currency || 'N/A'} - ${c.is_active ? 'Active' : 'Inactive'}`);
        });
      }
    }

    // Feeds
    const feedsCheck = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'feeds'
      );
    `);
    if (feedsCheck.rows[0].exists) {
      const feeds = await client.query('SELECT COUNT(*) as count FROM feeds');
      const feedsByCountry = await client.query(`
        SELECT 
          c.name AS country,
          COUNT(f.id) AS feed_count
        FROM country c
        LEFT JOIN feeds f ON c.id = f.fd_country_id
        GROUP BY c.name
        ORDER BY feed_count DESC
        LIMIT 10;
      `);
      console.log(`\n✅ Feeds table exists: ${feeds.rows[0].count} total feeds`);
      if (feedsByCountry.rows.length > 0) {
        console.log('   Feeds by country:');
        feedsByCountry.rows.forEach(f => {
          console.log(`     - ${f.country}: ${f.feed_count} feeds`);
        });
      }
    }

    // Users
    const usersCheck = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'user_information'
      );
    `);
    if (usersCheck.rows[0].exists) {
      const users = await client.query('SELECT COUNT(*) as count FROM user_information');
      const admins = await client.query('SELECT COUNT(*) as count FROM user_information WHERE is_admin = true');
      console.log(`\n✅ Users table exists: ${users.rows[0].count} total users, ${admins.rows[0].count} admins`);
    }

    // Check for multi-tenant tables (from our migration)
    const orgsCheck = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'organizations'
      );
    `);
    if (orgsCheck.rows[0].exists) {
      const orgs = await client.query('SELECT COUNT(*) as count FROM organizations');
      console.log(`\n✅ Organizations table exists: ${orgs.rows[0].count} organizations`);
    } else {
      console.log(`\n⚠️  Organizations table does NOT exist (multi-tenant migration not run yet)`);
    }

    const apiKeysCheck = await client.query(`
      SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'api_keys'
      );
    `);
    if (apiKeysCheck.rows[0].exists) {
      const keys = await client.query('SELECT COUNT(*) as count FROM api_keys');
      console.log(`\n✅ API Keys table exists: ${keys.rows[0].count} API keys`);
    } else {
      console.log(`\n⚠️  API Keys table does NOT exist (multi-tenant migration not run yet)`);
    }

    console.log('\n\n✅ Database review complete!');

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('\n❌ Database connection or query failed:', errorMessage);
    const errorCode = error?.code;
    if (errorCode === 'ETIMEDOUT' || errorCode === 'EHOSTUNREACH' || errorCode === 'ECONNREFUSED') {
      console.error('   This often means the database host is unreachable or the port is blocked.');
      console.error('   Check firewall settings and network connectivity.');
    } else if (errorCode === '28P01') {
      console.error('   Authentication failed. Check username and password.');
    } else if (errorCode === '3D000') {
      console.error('   Database does not exist.');
    }
    process.exit(1);
  } finally {
    await client.end();
    console.log('\n🔌 Database connection closed.');
  }
}

reviewDatabase();

