#!/usr/bin/env python3
"""
Immich WhatsApp Duplicate Cleaner

This script identifies and deletes duplicate images from WhatsApp folders in Immich.
It keeps the original image and deletes the WhatsApp version when duplicates are found.
"""

import json
import requests
import sys
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using environment variables only.")


class ImmichAPI:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

    def get_asset_duplicates(self) -> List[Dict[str, Any]]:
        """Fetch duplicate assets from Immich API"""
        url = f"{self.base_url}/api/duplicates"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching duplicates: {response.status_code} - {response.text}")
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


def is_whatsapp_asset(asset: Dict[str, Any]) -> bool:
    """Check if an asset is from WhatsApp based on path or filename"""
    original_path = asset.get('originalPath', '').lower()
    original_filename = asset.get('originalFileName', '').lower()
    
    # Check for common WhatsApp patterns
    whatsapp_indicators = [
        'whatsapp',
        'wa0',
        '/sent/',
        'img-', 
        '-wa0'
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
        if whatsapp_assets and non_whatsapp_assets:
            for wa_asset in whatsapp_assets:
                assets_to_delete.append(wa_asset['id'])
                print(f"  📱 WhatsApp duplicate: {wa_asset['originalFileName']}")
                print(f"     Path: {wa_asset['originalPath']}")
                print(f"     ID: {wa_asset['id']}")
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
    # Configuration from environment variables or .env file
    IMMICH_BASE_URL = os.getenv('IMMICH_BASE_URL', 'http://localhost:2283')
    IMMICH_API_KEY = os.getenv('IMMICH_API_KEY', '')
    DUPLICATES_FILE = os.getenv('DUPLICATES_FILE', 'duplicates.json')
    DRY_RUN = os.getenv('DRY_RUN', 'true').lower() in ('true', '1', 'yes')
    
    # Validate required configuration
    if not IMMICH_API_KEY:
        print("Error: IMMICH_API_KEY is required. Set it in .env file or as environment variable.")
        return
    
    print("Immich WhatsApp Duplicate Cleaner")
    print("=" * 40)
    
    # Option 1: Load from API
    # api = ImmichAPI(IMMICH_BASE_URL, IMMICH_API_KEY)
    # print("Fetching duplicates from Immich API...")
    # duplicates = api.get_asset_duplicates()
    
    # Option 2: Load from file (current approach)
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