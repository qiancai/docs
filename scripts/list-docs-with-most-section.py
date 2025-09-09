""" This scripts counts the number of sections in each .md file in the given path and all subdirectories recursively, then exports the result to a CSV file.

Before counting, the scripts removes all the comments (content wrapped by `<!--` and `-->`) in the .md file.

The CSV file will be saved to the `docs/` directory.

The CSV file will have the following columns:
- `doc_name`: The name of the doc.md file
- `relative_path`: The relative path of the file from the base directory
- `section_count`: The number of sections in the doc.md file
"""

import os
import re
import csv
import glob
from pathlib import Path

# Configuration
doc_path = r"/Users/grcai/Documents/GitHub/docs"
output_csv = os.path.join(doc_path, "section_count_report.csv")


def remove_html_comments(content):
    """Remove HTML comments from markdown content."""
    # Remove HTML comments (<!-- ... -->)
    # Use DOTALL flag to match across newlines
    return re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)


def count_sections(content):
    """Count the number of sections (headers) in markdown content."""
    # Remove HTML comments first
    clean_content = remove_html_comments(content)
    
    # Count headers (lines starting with #)
    # This matches # ## ### #### ##### ###### at the beginning of lines
    header_pattern = r'^#+\s+'
    headers = re.findall(header_pattern, clean_content, flags=re.MULTILINE)
    
    return len(headers)


def process_markdown_files(directory_path):
    """Process all .md files in the given directory and all subdirectories recursively."""
    results = []
    
    # Find all .md files recursively in the directory and all subdirectories
    md_pattern = os.path.join(directory_path, "**", "*.md")
    md_files = glob.glob(md_pattern, recursive=True)
    
    print(f"Found {len(md_files)} markdown files to process (including subdirectories)...")
    
    for file_path in md_files:
        try:
            # Get just the filename without path
            doc_name = os.path.basename(file_path)
            
            # Get relative path from the base directory for better identification
            relative_path = os.path.relpath(file_path, directory_path)
            
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count sections
            section_count = count_sections(content)
            
            results.append({
                'doc_name': doc_name,
                'relative_path': relative_path,
                'section_count': section_count
            })
            
            print(f"Processed {relative_path}: {section_count} sections")
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            continue
    
    return results


def export_to_csv(results, output_file):
    """Export results to CSV file."""
    # Sort results by section_count in descending order (most sections first)
    sorted_results = sorted(results, key=lambda x: x['section_count'], reverse=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['doc_name', 'relative_path', 'section_count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header
        writer.writeheader()
        
        # Write data
        for row in sorted_results:
            writer.writerow(row)
    
    print(f"Results exported to: {output_file}")
    return sorted_results


def main():
    """Main execution function."""
    print("Starting markdown section count analysis...")
    print(f"Scanning directory: {doc_path}")
    
    # Check if directory exists
    if not os.path.exists(doc_path):
        print(f"Error: Directory {doc_path} does not exist!")
        return
    
    # Process all markdown files
    results = process_markdown_files(doc_path)
    
    if not results:
        print("No markdown files found or processed successfully.")
        return
    
    # Export to CSV
    sorted_results = export_to_csv(results, output_csv)
    
    # Print summary
    print(f"\nSummary:")
    print(f"Total files processed: {len(results)}")
    print(f"Top 5 files with most sections:")
    for i, result in enumerate(sorted_results[:5], 1):
        print(f"{i}. {result['relative_path']}: {result['section_count']} sections")


if __name__ == "__main__":
    main()