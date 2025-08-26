#!/usr/bin/env python3
"""
Immich WhatsApp Duplicate Cleaner

This script identifies and deletes duplicate images from WhatsApp folders in Immich.
It keeps the original image and deletes the WhatsApp version when duplicates are found.

Safety features:
- Only deletes WhatsApp versions when non-WhatsApp originals exist
- Only deletes WhatsApp versions that are smaller (compressed) than originals
- Runs in dry-run mode by default
"""

import json
import requests
import sys
import os
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using environment variables only.")


class ImmichAPI:
    def __init__(self, base_url: str, api_key: str, cache_file: str = "duplicates.json"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.cache_file = cache_file
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

    def _is_cache_valid(self, max_age_hours: int = 24) -> bool:
        """Check if cache file exists and is not older than max_age_hours"""
        if not os.path.exists(self.cache_file):
            return False
        
        cache_stat = os.stat(self.cache_file)
        cache_age = datetime.now() - datetime.fromtimestamp(cache_stat.st_mtime)
        return cache_age < timedelta(hours=max_age_hours)

    def _save_cache(self, data: List[Dict[str, Any]]) -> None:
        """Save duplicates data to cache file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=None, separators=(',', ':'))
            print(f"✅ Cached duplicates data to {self.cache_file}")
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")

    def _load_cache(self) -> List[Dict[str, Any]]:
        """Load duplicates data from cache file"""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load cache: {e}")
            return []

    def get_asset_duplicates(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch duplicate assets from Immich API with caching
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh data
        """
        # Check if we can use cached data
        if not force_refresh and self._is_cache_valid():
            cache_stat = os.stat(self.cache_file)
            cache_time = datetime.fromtimestamp(cache_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"📁 Using cached duplicates data from {cache_time}")
            return self._load_cache()
        
        # Fetch fresh data from API
        print("🔄 Fetching duplicates from Immich API...")
        url = f"{self.base_url}/api/duplicates"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=300)  # 5 min timeout
            
            if response.status_code == 200:
                data = response.json()
                self._save_cache(data)
                return data
            else:
                print(f"Error fetching duplicates: {response.status_code} - {response.text}")
                
                # Fall back to cache if API fails and cache exists
                if os.path.exists(self.cache_file):
                    print(f"⚠️ API failed, falling back to cached data")
                    return self._load_cache()
                return []
                
        except requests.exceptions.Timeout:
            print("⏱️ API request timed out (5 minutes)")
            if os.path.exists(self.cache_file):
                print(f"⚠️ Falling back to cached data")
                return self._load_cache()
            return []
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            if os.path.exists(self.cache_file):
                print(f"⚠️ Falling back to cached data")
                return self._load_cache()
            return []

    def delete_assets(self, asset_ids: List[str]) -> bool:
        """Delete assets by their IDs"""
        if not asset_ids:
            return True
            
        url = f"{self.base_url}/api/assets"
        payload = {"ids": asset_ids}
        
        response = requests.delete(url, headers=self.headers, json=payload)
        
        if response.status_code == 204:
            return True
        else:
            print(f"Error deleting assets: {response.status_code} - {response.text}")
            return False


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def is_whatsapp_asset(asset: Dict[str, Any]) -> bool:
    """Check if an asset is from WhatsApp based on path or filename"""
    original_path = asset.get('originalPath', '').lower()
    original_filename = asset.get('originalFileName', '').lower()
    
    # Check for common WhatsApp patterns
    whatsapp_indicators = [
        'whatsapp',
        #'wa0',
        '/sent/',
        #'img-', 
        #'-wa0'
    ]
    
    path_and_filename = f"{original_path} {original_filename}".lower()
    
    return any(indicator in path_and_filename for indicator in whatsapp_indicators)


def find_whatsapp_duplicates_to_delete(duplicates: List[Dict[str, Any]]) -> List[str]:
    """
    Identify WhatsApp duplicates to delete.
    For each duplicate group, if there's a WhatsApp version and a non-WhatsApp version,
    mark the WhatsApp version for deletion.
    """
    assets_to_delete = []
    
    for duplicate_group in duplicates:
        assets = duplicate_group.get('assets', [])
        if len(assets) < 2:
            continue
            
        whatsapp_assets = []
        non_whatsapp_assets = []
        
        for asset in assets:
            if is_whatsapp_asset(asset):
                whatsapp_assets.append(asset)
            else:
                non_whatsapp_assets.append(asset)
        
        # Only delete WhatsApp assets if there are non-WhatsApp versions available
        # AND the WhatsApp version is smaller (compressed)
        if whatsapp_assets and non_whatsapp_assets:
            for wa_asset in whatsapp_assets:
                wa_file_size = wa_asset.get('exifInfo', {}).get('fileSizeInByte', 0)
                
                # Check if any non-WhatsApp version is larger
                has_larger_original = False
                largest_original_size = 0
                largest_original_name = ""
                
                for orig_asset in non_whatsapp_assets:
                    orig_file_size = orig_asset.get('exifInfo', {}).get('fileSizeInByte', 0)
                    if orig_file_size > wa_file_size:
                        has_larger_original = True
                        if orig_file_size > largest_original_size:
                            largest_original_size = orig_file_size
                            largest_original_name = orig_asset['originalFileName']
                
                if has_larger_original:
                    assets_to_delete.append(wa_asset['id'])
                    print(f"  📱 WhatsApp duplicate: {wa_asset['originalFileName']}")
                    print(f"     Path: {wa_asset['originalPath']}")
                    print(f"     Size: {format_file_size(wa_file_size)} (compressed)")
                    print(f"     Original: {largest_original_name} ({format_file_size(largest_original_size)})")
                    print(f"     ID: {wa_asset['id']}")
                    print()
                else:
                    print(f"  ⚠️  Skipping: {wa_asset['originalFileName']}")
                    print(f"     Reason: WhatsApp version ({format_file_size(wa_file_size)}) is not smaller than original")
                    print()
                
    if assets_to_delete:
        print(f"\n{'='*60}")
        print(f"SUMMARY: Found {len(assets_to_delete)} WhatsApp duplicates to delete")
        print(f"{'='*60}")
    
    return assets_to_delete


def load_duplicates_from_file(filename: str) -> List[Dict[str, Any]]:
    """Load duplicates from JSON file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file: {e}")
        return []


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Clean WhatsApp duplicate images from Immich')
    parser.add_argument('--refresh', action='store_true', 
                       help='Force refresh duplicates from API (ignore cache)')
    parser.add_argument('--no-api', action='store_true', 
                       help='Use local duplicates.json file only (don\'t use API)')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually delete files (disable dry-run mode)')
    args = parser.parse_args()
    
    # Configuration from environment variables or .env file, with CLI overrides
    IMMICH_BASE_URL = os.getenv('IMMICH_BASE_URL', 'http://localhost:2283')
    IMMICH_API_KEY = os.getenv('IMMICH_API_KEY', '')
    DUPLICATES_FILE = os.getenv('DUPLICATES_FILE', 'duplicates.json')
    DRY_RUN = not args.execute and os.getenv('DRY_RUN', 'true').lower() in ('true', '1', 'yes')
    FORCE_REFRESH = args.refresh or os.getenv('FORCE_REFRESH', 'false').lower() in ('true', '1', 'yes')
    USE_API = not args.no_api and os.getenv('USE_API', 'true').lower() in ('true', '1', 'yes')
    
    print("Immich WhatsApp Duplicate Cleaner")
    print("=" * 40)
    
    # Load duplicates data
    if USE_API:
        # Validate required configuration for API usage
        if not IMMICH_API_KEY:
            print("Error: IMMICH_API_KEY is required when USE_API=true.")
            print("Set it in .env file or set USE_API=false to use local file only.")
            return
        
        # Use API with caching
        api = ImmichAPI(IMMICH_BASE_URL, IMMICH_API_KEY, DUPLICATES_FILE)
        duplicates = api.get_asset_duplicates(force_refresh=FORCE_REFRESH)
    else:
        # Load from file only (fallback mode)
        print(f"Loading duplicates from {DUPLICATES_FILE}...")
        duplicates = load_duplicates_from_file(DUPLICATES_FILE)
    
    if not duplicates:
        print("No duplicates found or error loading data")
        return
    
    print(f"Found {len(duplicates)} duplicate groups")
    print(f"Dry run mode: {'ENABLED' if DRY_RUN else 'DISABLED'}")
    print()
    
    # Find WhatsApp duplicates to delete
    print("Analyzing duplicates for WhatsApp versions...")
    assets_to_delete = find_whatsapp_duplicates_to_delete(duplicates)
    
    if not assets_to_delete:
        print("\nNo WhatsApp duplicates found that have non-WhatsApp alternatives")
        return
    
    if DRY_RUN:
        print(f"\n🔍 DRY RUN MODE - No files will be deleted")
        print(f"To actually delete files, set DRY_RUN=false in your .env file")
        print(f"The following {len(assets_to_delete)} files would be deleted:\n")
        return
    else:
        print("\n*** WARNING: This will permanently delete files ***")
        confirm = input("Are you sure you want to continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Cancelled by user")
            return
        
        # Initialize API for actual deletion
        api = ImmichAPI(IMMICH_BASE_URL, IMMICH_API_KEY)
        
        # Delete in batches to avoid overwhelming the API
        batch_size = 50
        total_deleted = 0
        
        for i in range(0, len(assets_to_delete), batch_size):
            batch = assets_to_delete[i:i + batch_size]
            print(f"Deleting batch {i//batch_size + 1} ({len(batch)} assets)...")
            
            if api.delete_assets(batch):
                total_deleted += len(batch)
                print(f"Successfully deleted {len(batch)} assets")
            else:
                print(f"Failed to delete batch {i//batch_size + 1}")
                break
        
        print(f"\nCompleted: {total_deleted} assets deleted")


if __name__ == "__main__":
    main()
