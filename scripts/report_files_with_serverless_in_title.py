#!/usr/bin/env python3
"""
Script to find .md files in tidb-cloud directory that have "TiDB Cloud Serverless"
in their level-1 headers (# title), excluding those with "TiDB Cloud Serverless Driver"
"""

import os
import re
from pathlib import Path

def search_files_with_serverless_in_title():
    """
    Search for .md files that have "TiDB Cloud Serverless" in level-1 headers
    but exclude those with "TiDB Cloud Serverless Driver" in the title
    """
    base_dir = Path("/Users/grcai/Documents/GitHub/docs/tidb-cloud")
    matching_files = []
    
    # Pattern to match level-1 headers with "TiDB Cloud Serverless"
    # ^# matches start of line with #, then any text containing "TiDB Cloud Serverless"
    title_pattern = re.compile(r'^#\s+.*TiDB Cloud Serverless.*$', re.MULTILINE | re.IGNORECASE)
    # Pattern to exclude titles with "TiDB Cloud Serverless Driver"
    driver_pattern = re.compile(r'TiDB Cloud Serverless Driver', re.IGNORECASE)
    
    # Walk through all .md files in the tidb-cloud directory
    for file_path in base_dir.rglob("*.md"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Find all level-1 headers that contain "TiDB Cloud Serverless"
                title_matches = title_pattern.findall(content)
                
                if title_matches:
                    # Check if any of the matching titles do NOT contain "Driver"
                    has_valid_title = False
                    for title in title_matches:
                        if not driver_pattern.search(title):
                            has_valid_title = True
                            break
                    
                    if has_valid_title:
                        # Get relative path from docs directory
                        relative_path = file_path.relative_to(Path("/Users/grcai/Documents/GitHub/docs"))
                        matching_files.append(str(relative_path))
                        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
    
    return matching_files

def main():
    """Main function to execute the search and print results"""
    matching_files = search_files_with_serverless_in_title()
    
    # Format the output as requested: [file1.md, file2.md]
    if matching_files:
        formatted_output = "[" + ", ".join(matching_files) + "]"
        print(formatted_output)
        print(len(matching_files))
    else:
        print("[]")

if __name__ == "__main__":
    main()
