# Immich WhatsApp Duplicate Cleaner

A Python script to automatically identify and delete WhatsApp duplicate images in your Immich photo library. The script keeps the original high-quality image and removes the compressed WhatsApp version.

## Features

- 🔍 Identifies duplicate images where one version is from WhatsApp and another is the original
- 🛡️ **Safe by default** - runs in dry-run mode to show what would be deleted
- 📱 Detects WhatsApp images by path patterns (`whatsapp`, `sent`, `wa0`, etc.)
- 🚀 **Smart caching** - caches API responses for 24 hours to avoid slow repeated calls
- 🔄 Can work with existing `duplicates.json` file or fetch directly from Immich API
- ⚡ Batch deletion for better performance

## Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` file with your settings:
```env
IMMICH_BASE_URL=http://localhost:2283
IMMICH_API_KEY=your-api-key-here
DUPLICATES_FILE=duplicates.json
DRY_RUN=true
USE_API=true
FORCE_REFRESH=false
```

### Getting your Immich API Key

1. Log into your Immich web interface
2. Go to Account Settings (top right profile icon)
3. Navigate to "API Keys" section
4. Click "New API Key" 
5. Give it a name and copy the generated key

## Usage

### Basic Usage

```bash
# Run with cached data (default behavior)
python delete_whatsapp_duplicates.py

# Force refresh from API (ignores 24-hour cache)
python delete_whatsapp_duplicates.py --refresh

# Use local file only (don't use API)
python delete_whatsapp_duplicates.py --no-api

# Actually delete files (disable dry-run)
python delete_whatsapp_duplicates.py --execute
```

### Caching Behavior

The script uses intelligent caching to speed up repeated runs:

- **First run**: Fetches duplicates from Immich API and saves to `duplicates.json`
- **Subsequent runs**: Uses cached data if less than 24 hours old
- **Cache refresh**: Automatically refreshes cache after 24 hours or use `--refresh`

### Configuration Options

- `USE_API=true`: Use Immich API with caching (default)
- `USE_API=false`: Use local `duplicates.json` file only
- `FORCE_REFRESH=true`: Always fetch fresh data from API

## Safety Features

- **Dry run by default**: The script will only show what would be deleted unless you set `DRY_RUN=false`
- **File size comparison**: Only deletes WhatsApp versions that are smaller (compressed) than their originals
- **Confirmation prompt**: When not in dry run mode, asks for confirmation before deleting
- **Batch processing**: Deletes files in batches to avoid overwhelming the API
- **Conservative logic**: Only deletes WhatsApp versions when non-WhatsApp versions exist

## What gets detected as WhatsApp?

The script identifies WhatsApp images by looking for these patterns in file paths and names:
- `whatsapp` (case insensitive)
- `wa0` (WhatsApp file naming pattern)
- `/sent/` (WhatsApp sent folder)
- `img-` followed by `wa` (WhatsApp image naming)

## Example Output

```
Immich WhatsApp Duplicate Cleaner
========================================
Loading duplicates from duplicates.json...
Found 1234 duplicate groups
Dry run mode: ENABLED

Analyzing duplicates for WhatsApp versions...
  📱 WhatsApp duplicate: IMG-20231014-WA0013.jpg
     Path: /path/to/whatsapp/sent/IMG-20231014-WA0013.jpg
     Size: 377.8 KB (compressed)
     Original: PXL_20231014_171942197.jpg (3.1 MB)
     ID: a010301e-9ed9-4183-8fc3-05a273d27289

============================================================
SUMMARY: Found 1 WhatsApp duplicates to delete
============================================================

🔍 DRY RUN MODE - No files will be deleted
To actually delete files, set DRY_RUN=false in your .env file
```

## Running with actual deletion

⚠️ **Warning**: This will permanently delete files from your Immich library.

1. Set `DRY_RUN=false` in your `.env` file
2. Run the script: `python delete_whatsapp_duplicates.py`
3. Confirm when prompted

## License

MIT License