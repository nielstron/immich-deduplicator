# Immich WhatsApp Duplicate Cleaner

A Python script to automatically identify and delete duplicate images in your Immich photo library.

The script is designed to run in bulk and delete everything following some simple rules. So far, the only implemented rule is to delete WhatsApp images that are detected as duplicates (i.e., when sent). The script keeps the original high-quality image and removes the compressed WhatsApp version.


The script is **Safe by default** - runs in dry-run mode to show what would be deleted.
Since the duplicates endpoint is usually slow, it by default caches the response for 24 hours.

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

## Usage

### Basic Usage

```bash
# Run using env config (default behavior)
python delete_whatsapp_duplicates.py

# Force refresh from API (ignores 24-hour cache)
python delete_whatsapp_duplicates.py --refresh

# Use local file only (don't use API)
python delete_whatsapp_duplicates.py --no-api

# Actually delete files (disable dry-run)
python delete_whatsapp_duplicates.py --execute
```

### Caching Behavior

The script uses caching to speed up repeated runs:

- **First run**: Fetches duplicates from Immich API and saves to `$DUPLICATES_FILE`
- **Subsequent runs**: Uses cached data if less than 24 hours old
- **Cache refresh**: Automatically refreshes cache after 24 hours or use `--refresh`

## What gets detected as WhatsApp?

The script identifies WhatsApp images by looking for these patterns in file paths and names:
- `whatsapp images` (case insensitive)
- `/sent/` (WhatsApp sent folder)

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
