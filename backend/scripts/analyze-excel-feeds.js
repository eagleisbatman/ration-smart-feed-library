#!/usr/bin/env node

/**
 * Detailed Analysis of Excel Feed Data
 * Analyzes the Excel file to understand why feeds are being skipped
 */

import XLSX from 'xlsx';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const EXCEL_FILE = join(__dirname, '../../../Analysed chemical composition of feeds (highlighted for compound feeds, horticultural wastes and agroindustrial byproducts).xls');

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
    rowIndex: rowIndex + 2, // Excel row number
    sheetName: sheetName,
    columns: columns
  };
}

console.log('📊 Analyzing Excel File...\n');

const workbook = XLSX.readFile(EXCEL_FILE);
const allFeeds = [];
const skippedFeeds = [];
const stats = {
  totalRows: 0,
  validFeeds: 0,
  missingName: 0,
  missingDM: 0,
  hasDM: 0
};

workbook.SheetNames.forEach((sheetName) => {
  console.log(`\n📋 Sheet: "${sheetName}"`);
  const worksheet = workbook.Sheets[sheetName];
  const data = XLSX.utils.sheet_to_json(worksheet, { defval: null });
  
  stats.totalRows += data.length;
  console.log(`   Total rows: ${data.length}`);
  
  // Show column names
  if (data.length > 0) {
    console.log(`   Columns: ${Object.keys(data[0]).slice(0, 10).join(', ')}...`);
  }
  
  data.forEach((row, index) => {
    try {
      const feedData = transformRow(row, sheetName, index);
      
      if (!feedData.fd_name_default || feedData.fd_name_default === 'null' || feedData.fd_name_default === 'undefined') {
        stats.missingName++;
        skippedFeeds.push({
          sheet: sheetName,
          row: index + 2,
          reason: 'Missing feed name',
          data: Object.keys(row).slice(0, 5)
        });
        return;
      }
      
      if (!feedData.fd_dm || feedData.fd_dm === null) {
        stats.missingDM++;
        skippedFeeds.push({
          sheet: sheetName,
          row: index + 2,
          reason: 'Missing DM value',
          name: feedData.fd_name_default
        });
        return;
      }
      
      stats.hasDM++;
      stats.validFeeds++;
      allFeeds.push(feedData);
    } catch (error) {
      skippedFeeds.push({
        sheet: sheetName,
        row: index + 2,
        reason: `Error: ${error.message}`
      });
    }
  });
});

console.log('\n\n📊 SUMMARY:');
console.log(`   Total rows processed: ${stats.totalRows}`);
console.log(`   Valid feeds (has name + DM): ${stats.validFeeds}`);
console.log(`   Missing feed name: ${stats.missingName}`);
console.log(`   Missing DM value: ${stats.missingDM}`);
console.log(`   Has DM value: ${stats.hasDM}`);

console.log('\n\n📋 Sample skipped feeds (first 20):');
skippedFeeds.slice(0, 20).forEach((skip, i) => {
  console.log(`   ${i+1}. Sheet: ${skip.sheet}, Row: ${skip.row}, Reason: ${skip.reason}`);
  if (skip.name) console.log(`      Name: ${skip.name}`);
});

console.log(`\n\n✅ Valid feeds ready for import: ${allFeeds.length}`);
console.log('\n📋 Sample valid feeds (first 10):');
allFeeds.slice(0, 10).forEach((feed, i) => {
  console.log(`   ${i+1}. ${feed.fd_name_default} (${feed.fd_type}) - DM: ${feed.fd_dm}%`);
});

// Check for duplicates
const nameMap = {};
const duplicates = [];
allFeeds.forEach(feed => {
  const key = `${feed.fd_name_default.toLowerCase()}_${feed.fd_type}_${feed.fd_category}`;
  if (nameMap[key]) {
    duplicates.push(feed);
  } else {
    nameMap[key] = feed;
  }
});

console.log(`\n\n🔍 Duplicate check:`);
console.log(`   Unique feeds: ${Object.keys(nameMap).length}`);
console.log(`   Potential duplicates: ${duplicates.length}`);

if (duplicates.length > 0) {
  console.log('\n   Sample duplicates:');
  duplicates.slice(0, 5).forEach((dup, i) => {
    console.log(`   ${i+1}. ${dup.fd_name_default} (${dup.fd_type})`);
  });
}

