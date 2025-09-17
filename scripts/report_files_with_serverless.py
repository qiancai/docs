#!/usr/bin/env python3
"""
Script to find files containing "TiDB Cloud Serverless" (misspelled) 
in the tidb-cloud directory, excluding "TiDB Cloud Serverless Driver"
"""

import os
import re
from pathlib import Path

def search_files_with_Serverless():
    """
    Search for files containing "TiDB Cloud Serverless" (misspelled)
    but not "TiDB Cloud Serverless Driver"
    """
    base_dir = Path("/Users/grcai/Documents/GitHub/docs/tidb-cloud")
    matching_files = []
    
    # Pattern to match "TiDB Cloud Serverless" (note the missing 'r')
    Serverless_pattern = re.compile(r'TiDB Cloud Serverless', re.IGNORECASE)
    # Pattern to exclude "TiDB Cloud Serverless Driver"
    driver_pattern = re.compile(r'TiDB Cloud Serverless Driver', re.IGNORECASE)
    
    # Walk through all files in the tidb-cloud directory
    for file_path in base_dir.rglob("*.md"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check if file contains the misspelled "TiDB Cloud Serverless"
                if Serverless_pattern.search(content):
                    # But exclude if it only contains "TiDB Cloud Serverless Driver"
                    # We need to check if there's a standalone "TiDB Cloud Serverless" not part of "Driver"
                    
                    # Find all matches of the misspelled version
                    Serverless_matches = Serverless_pattern.findall(content)
                    
                    # Check if any match is NOT part of "TiDB Cloud Serverless Driver"
                    has_standalone_Serverless = False
                    for match_start in [m.start() for m in Serverless_pattern.finditer(content)]:
                        # Check if this match is followed by " Driver"
                        match_end = match_start + len("TiDB Cloud Serverless")
                        following_text = content[match_end:match_end + 7]  # " Driver"
                        
                        if not following_text.strip().lower().startswith("driver"):
                            has_standalone_Serverless = True
                            break
                    
                    if has_standalone_Serverless:
                        # Get relative path from docs directory
                        relative_path = file_path.relative_to(Path("/Users/grcai/Documents/GitHub/docs"))
                        matching_files.append(str(relative_path))
                        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
    
    return matching_files

def main():
    """Main function to execute the search and print results"""
    matching_files = search_files_with_Serverless()
    
    # Format the output as requested: [file1.md, file2.md]
    if matching_files:
        formatted_output = "[" + ", ".join(matching_files) + "]"
        print(formatted_output)
    else:
        print("[]")

if __name__ == "__main__":
    main()
