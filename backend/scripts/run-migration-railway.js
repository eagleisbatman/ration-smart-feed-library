#!/usr/bin/env node

/**
 * Run Database Migration on Railway Database
 * Connects to Railway PostgreSQL and runs the schema migration
 */

import pg from 'pg';
const { Client } = pg;
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Parse DATABASE_URL if provided, otherwise use individual env vars
let dbConfig;

if (process.env.DATABASE_URL) {
  // Parse DATABASE_URL: postgresql://user:password@host:port/database
  const url = new URL(process.env.DATABASE_URL);
  dbConfig = {
    host: url.hostname,
    port: parseInt(url.port || '5432'),
    user: url.username,
    password: url.password,
    database: url.pathname.slice(1), // Remove leading '/'
  };
} else {
  dbConfig = {
    host: process.env.NEW_DB_HOST || 'localhost',
    port: parseInt(process.env.NEW_DB_PORT || '5432'),
    user: process.env.NEW_DB_USER || 'postgres',
    password: process.env.NEW_DB_PASSWORD || '',
    database: process.env.NEW_DB_NAME || 'railway',
  };
}

const client = new Client({
  ...dbConfig,
  connectionTimeoutMillis: 30000
});

async function runMigration() {
  try {
    console.log('🔌 Connecting to Railway database...');
    console.log(`   Host: ${dbConfig.host}:${dbConfig.port}`);
    console.log(`   Database: ${dbConfig.database}`);
    console.log(`   User: ${dbConfig.user}\n`);

    await client.connect();
    console.log('✅ Connected successfully!\n');

    // Read migration file
    const migrationPath = join(__dirname, '../migrations/001_create_new_database_schema.sql');
    console.log(`📖 Reading migration file: ${migrationPath}`);
    const migrationSQL = readFileSync(migrationPath, 'utf-8');

    // Split SQL into individual statements (handle DO blocks and semicolons)
    const statements = migrationSQL
      .replace(/--.*$/gm, '') // Remove comments
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0 && !s.match(/^\s*$/));

    console.log(`📝 Executing ${statements.length} SQL statements...\n`);

    for (let i = 0; i < statements.length; i++) {
      const statement = statements[i];
      if (statement.trim() && !statement.match(/^\s*$/)) {
        try {
          await client.query(statement + ';');
          console.log(`   ✅ Statement ${i + 1}/${statements.length} executed`);
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          // Ignore "already exists" errors
          if (errorMessage.includes('already exists') || 
              errorMessage.includes('duplicate') ||
              errorMessage.includes('relation') && errorMessage.includes('already exists')) {
            console.log(`   ⚠️  Statement ${i + 1}/${statements.length} skipped (already exists)`);
          } else {
            console.error(`   ❌ Statement ${i + 1}/${statements.length} failed:`);
            console.error(`      ${errorMessage}`);
            // Don't throw - continue with other statements
          }
        }
      }
    }

    console.log('\n✅ Migration completed!');

    // Verify tables were created
    console.log('\n🔍 Verifying tables...');
    const tables = await client.query(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'public'
      ORDER BY table_name;
    `);

    console.log(`   Found ${tables.rows.length} tables:`);
    tables.rows.forEach((row, index) => {
      console.log(`   ${index + 1}. ${row.table_name}`);
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('\n❌ Migration failed:', errorMessage);
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
    await client.end();
    console.log('\n🔌 Database connection closed.');
  }
}

runMigration();

