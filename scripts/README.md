# Database Migration Scripts

## upgrade_db.py

**Status**: ✅ Already executed  
**Purpose**: One-time migration to multi-tenant schema  
**Date**: Migrated existing database to support multiple users

### ⚠️ WARNING

**DO NOT run this script again** unless you are rolling back the database to a previous state.

This script was used to migrate from single-tenant to multi-tenant architecture by:

- Adding `user_id` column to `products` table
- Adding `user_id` column to `stock_movements` table
- Migrating existing data to user_id = 1
- Adding foreign key constraints

### Usage (if needed for reference)

```bash
python scripts/upgrade_db.py
```

The script is idempotent and will check if migration is already complete before making changes.
