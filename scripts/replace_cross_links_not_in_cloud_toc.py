#!/usr/bin/env python3
"""
This script converts internal markdown links that are not referenced in TOC-tidb-cloud.md to HTTP links.

It reads the TOC file to identify which pages are included in the cloud documentation,
then processes only those markdown files to convert links to pages not in the TOC to external HTTP links.
"""

import os
import re
import sys
from pathlib import Path

# Configuration - Edit these values as needed
# ==========================================
# Path to the TOC file for TiDB Cloud
cloud_toc_path = r"/Users/grcai/Documents/GitHub/docs/TOC-tidb-cloud.md"

# Base URL for external links
base_url = "https://docs.pingcap.com/tidbcloud"
base_url2 = "https://docs.pingcap.com/tidb/stable"

# Whether to perform a dry run (True) or actually modify files (False)
dry_run = False
# ==========================================

def extract_toc_links_and_files(toc_path):
    """Extract all links from the TOC file and return both normalized links and file paths."""
    if not os.path.exists(toc_path):
        print(f"Error: TOC file not found at {toc_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(toc_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Error: Could not read TOC file as UTF-8: {toc_path}", file=sys.stderr)
        sys.exit(1)
    
    # Extract all markdown links from the TOC
    link_pattern = r'\[.*?\]\((.*?)\)'
    links = re.findall(link_pattern, content)
    
    # Normalize links and collect file paths
    normalized_links = set()
    file_paths = set()
    
    for link in links:
        # Remove anchor if present
        clean_link = link.split('#')[0]
        
        # Skip external links
        if clean_link.startswith(('http', 'https')):
            continue
            
        # Ensure link starts with /
        if clean_link and not clean_link.startswith('/'):
            clean_link = '/' + clean_link
        
        normalized_links.add(clean_link)
        
        # Extract file path
        if clean_link:
            # Remove leading slash for file path
            if clean_link.startswith('/'):
                file_path = clean_link[1:]
            else:
                file_path = clean_link
                
            # Get the base directory of the TOC file
            toc_dir = os.path.dirname(os.path.abspath(toc_path))
            full_path = os.path.join(toc_dir, file_path)
            
            if os.path.exists(full_path):
                # Only add if it's a markdown file
                if full_path.lower().endswith('.md'):
                    file_paths.add(full_path)
    
    return normalized_links, file_paths

def is_binary_file(file_path):
    """Check if a file is binary by reading the first few bytes."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk  # Binary files often contain null bytes
    except Exception:
        return True  # If we can't read the file, assume it's binary

def format_url_path(path):
    """Format a file path to be used in a URL."""
    # Remove .md extension if present
    if path.lower().endswith('.md'):
        path = path[:-3]
    
    # Handle special cases for index files
    if path.endswith('/index'):
        path = path[:-6]  # Remove '/index'
    elif path == 'index':
        path = ''
    
    return path

def process_markdown_file(file_path, toc_links, base_url, base_url2, dry_run):
    """Process a markdown file to replace links not in TOC."""
    # Skip binary files
    if is_binary_file(file_path):
        print(f"Skipping binary file: {file_path}")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Skipping file with non-UTF-8 encoding: {file_path}")
        return
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return
    
    # Find all markdown links in the file
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    
    def replace_link(match):
        text, link = match.groups()
        
        # Skip external links, image links, and anchor links
        if link.startswith(('http', 'https', '#', 'mailto:')):
            return match.group(0)
        
        # Skip image links (links that start with !)
        if text.startswith('!'):
            return match.group(0)
            
        # Skip links that don't point to .md files
        if not link.lower().endswith('.md') and '.' in link:
            return match.group(0)
        
        # Remove anchor for comparison
        comparison_link = link.split('#')[0]
        anchor = link[len(comparison_link):] if len(link) > len(comparison_link) else ''
        
        # Normalize link for comparison
        if not comparison_link.startswith('/'):
            comparison_link = '/' + comparison_link
        
        # If link is not in TOC, replace it with HTTP link
        if comparison_link not in toc_links:
            # Remove leading slash for URL construction
            if comparison_link.startswith('/'):
                comparison_link = comparison_link[1:]
            
            # Format the URL path properly
            url_path = format_url_path(comparison_link)
            
            # For TiDB documentation, we typically use the last part of the path as the URL slug
            # This removes directory structure like sql-statements/
            path_parts = url_path.split('/')
            simplified_path = path_parts[-1] if path_parts else ''
            
            # Use base_url for tidb-cloud links, base_url2 for other links
            if comparison_link.startswith('tidb-cloud/'):
                new_link = f"{base_url}/{simplified_path}{anchor}"
            else:
                new_link = f"{base_url2}/{simplified_path}{anchor}"
            
            return f"[{text}]({new_link})"
        
        return match.group(0)
    
    new_content = re.sub(link_pattern, replace_link, content)
    
    if new_content != content:
        if dry_run:
            print(f"Would update: {file_path}")
        else:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated: {file_path}")
            except Exception as e:
                print(f"Error writing to file {file_path}: {e}")
    else:
        print(f"No changes needed: {file_path}")

def main():
    print("Starting cross-link conversion process...")
    print(f"TOC file: {cloud_toc_path}")
    print(f"Base URL: {base_url}")
    print(f"Base URL2: {base_url2}")
    print(f"Dry run: {dry_run}")
    
    # Extract links and files from TOC
    toc_links, toc_files = extract_toc_links_and_files(cloud_toc_path)
    print(f"Found {len(toc_links)} links in TOC file")
    print(f"Found {len(toc_files)} markdown files referenced in TOC")
    
    # Process only the files referenced in the TOC
    for file_path in toc_files:
        process_markdown_file(file_path, toc_links, base_url, base_url2, dry_run)
    
    if dry_run:
        print("\nThis was a dry run. No files were modified.")
    else:
        print("\nAll files processed successfully.")

if __name__ == "__main__":
    main()