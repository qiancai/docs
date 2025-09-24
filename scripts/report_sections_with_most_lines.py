# This script analyzes .md files in the target path (including .md files in subdirectories) and generates reports for:
# 1. Top 200 sections with the most lines (CSV + Markdown)
# 2. Top 200 sections with the most characters (Markdown)
# 3. Top 200 sections with the most tokens using GPT-4 tokenizer (Markdown)

# Note that counts for each section only include lines/characters/tokens in the section itself, 
# not in the section's sub-sections.

# The CSV header is:
# doc name, section_name, number_of_lines

import os
import re
import csv
from collections import defaultdict
import tiktoken

target_path = "/Users/grcai/Documents/GitHub/docs"
#exclude_paths = ["releases"] # exclude the releases directory in the target path when counting the lines
exclude_paths = [] # exclude the releases directory in the target path when counting the lines
exclude_files = ["sections_with_most_lines.md", "sections_with_most_characters.md", "sections_with_most_tokens.md"]

def is_excluded_path(file_path, exclude_paths):
    """Check if the file path contains any excluded directories."""
    for exclude_path in exclude_paths:
        if exclude_path in file_path.split(os.sep):
            return True
    return False

def parse_markdown_sections(content, file_name):
    """Parse markdown content and extract sections with line counts, character counts, and token counts."""
    lines = content.split('\n')
    sections = []
    current_section = None
    current_section_lines = 0
    current_section_chars = 0
    current_section_tokens = 0
    current_level = 0
    
    # Initialize tiktoken encoder
    enc = tiktoken.get_encoding("cl100k_base")
    
    for line_num, line in enumerate(lines):
        # Check if line is a header (starts with #)
        header_match = re.match(r'^(#{1,6})\s*(.*)', line.strip())
        
        if header_match:
            # Save previous section if it exists
            if current_section is not None:
                sections.append({
                    'doc_name': file_name,
                    'section_name': current_section,
                    'line_count': current_section_lines,
                    'char_count': current_section_chars,
                    'token_count': current_section_tokens
                })
            
            # Start new section
            header_level = len(header_match.group(1))
            section_name = header_match.group(2).strip()
            current_section = section_name
            current_section_lines = 0
            current_section_chars = 0
            current_section_tokens = 0
            current_level = header_level
            
        elif current_section is not None:
            # Check if this line belongs to a sub-section (higher level header)
            sub_header_match = re.match(r'^(#{1,6})\s*(.*)', line.strip())
            if sub_header_match:
                sub_level = len(sub_header_match.group(1))
                if sub_level > current_level:
                    # This is a sub-section, don't count its lines for current section
                    continue
            
            # Count non-empty lines and lines that are not sub-section headers
            if line.strip():  # Only count non-empty lines
                current_section_lines += 1
                current_section_chars += len(line.strip())
                # Calculate tokens for this line
                line_tokens = enc.encode(line.strip())
                current_section_tokens += len(line_tokens)
    
    # Don't forget the last section
    if current_section is not None:
        sections.append({
            'doc_name': file_name,
            'section_name': current_section,
            'line_count': current_section_lines,
            'char_count': current_section_chars,
            'token_count': current_section_tokens
        })
    
    return sections

def create_section_anchor(section_name):
    """Create a markdown anchor from section name."""
    # Convert to lowercase and replace spaces/special chars with hyphens
    anchor = re.sub(r'[^a-zA-Z0-9\s-]', '', section_name.lower())
    anchor = re.sub(r'\s+', '-', anchor.strip())
    anchor = re.sub(r'-+', '-', anchor)  # Remove multiple consecutive hyphens
    return anchor.strip('-')

def write_markdown_report(sections, output_file='sections_with_most_lines.md'):
    """Write the sections report as a markdown file with clickable links."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Sections with Most Lines Report\n\n")
        f.write("This report shows the top sections from markdown files ordered by line count.\n\n")
        f.write("| Rank | Document | Section | Lines |\n")
        f.write("|------|----------|---------|-------|\n")
        
        for i, section in enumerate(sections, 1):
            doc_name = section['doc_name']
            section_name = section['section_name']
            line_count = section['line_count']
            
            # Create the section anchor
            section_anchor = create_section_anchor(section_name)
            
            # Create the clickable link - format: [Section Name](file.md#section-anchor)
            if section_anchor:
                section_link = f"[{section_name}]({doc_name}#{section_anchor})"
            else:
                # Fallback to just file link if anchor creation fails
                section_link = f"[{section_name}]({doc_name})"
            
            f.write(f"| {i} | {doc_name} | {section_link} | {line_count} |\n")
        
        f.write(f"\n---\n*Report generated from {len(sections)} sections*\n")

def write_character_markdown_report(sections, output_file='sections_with_most_characters.md'):
    """Write the sections character count report as a markdown file with clickable links."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Sections with Most Characters Report\n\n")
        f.write("This report shows the top sections from markdown files ordered by character count.\n\n")
        f.write("| Rank | Document | Section | Characters |\n")
        f.write("|------|----------|---------|------------|\n")
        
        for i, section in enumerate(sections, 1):
            doc_name = section['doc_name']
            section_name = section['section_name']
            char_count = section['char_count']
            
            # Create the section anchor
            section_anchor = create_section_anchor(section_name)
            
            # Create the clickable link - format: [Section Name](file.md#section-anchor)
            if section_anchor:
                section_link = f"[{section_name}]({doc_name}#{section_anchor})"
            else:
                # Fallback to just file link if anchor creation fails
                section_link = f"[{section_name}]({doc_name})"
            
            f.write(f"| {i} | {doc_name} | {section_link} | {char_count} |\n")
        
        f.write(f"\n---\n*Report generated from {len(sections)} sections*\n")

def write_token_markdown_report(sections, output_file='sections_with_most_tokens.md'):
    """Write the sections token count report as a markdown file with clickable links."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Sections with Most Tokens Report\n\n")
        f.write("This report shows the top sections from markdown files ordered by token count (using GPT-4 tokenizer).\n\n")
        f.write("| Rank | Document | Section | Tokens |\n")
        f.write("|------|----------|---------|--------|\n")
        
        for i, section in enumerate(sections, 1):
            doc_name = section['doc_name']
            section_name = section['section_name']
            token_count = section['token_count']
            
            # Create the section anchor
            section_anchor = create_section_anchor(section_name)
            
            # Create the clickable link - format: [Section Name](file.md#section-anchor)
            if section_anchor:
                section_link = f"[{section_name}]({doc_name}#{section_anchor})"
            else:
                # Fallback to just file link if anchor creation fails
                section_link = f"[{section_name}]({doc_name})"
            
            f.write(f"| {i} | {doc_name} | {section_link} | {token_count} |\n")
        
        f.write(f"\n---\n*Report generated from {len(sections)} sections*\n")

def find_markdown_files(target_path, exclude_paths):
    """Find all .md files in the target path, excluding specified paths."""
    md_files = []
    
    for root, dirs, files in os.walk(target_path):
        # Remove excluded directories from dirs to prevent os.walk from entering them
        dirs[:] = [d for d in dirs if not is_excluded_path(os.path.join(root, d), exclude_paths)]
        
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                if not is_excluded_path(file_path, exclude_paths) and file not in exclude_files:
                    md_files.append(file_path) 
    
    return md_files

def main():
    """Main function to process all markdown files and generate CSV report."""
    all_sections = []
    
    # Find all markdown files
    md_files = find_markdown_files(target_path, exclude_paths)
    print(f"Found {len(md_files)} markdown files to process...")
    
    # Process each markdown file
    for file_path in md_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Get relative file name for reporting
            rel_path = os.path.relpath(file_path, target_path)
            
            # Parse sections and count lines
            sections = parse_markdown_sections(content, rel_path)
            all_sections.extend(sections)
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    # Sort sections by line count (descending) and take top 200
    all_sections.sort(key=lambda x: x['line_count'], reverse=True)
    top_sections_lines = all_sections[:200]
    
    # Sort sections by character count (descending) and take top 200
    all_sections.sort(key=lambda x: x['char_count'], reverse=True)
    top_sections_chars = all_sections[:200]
    
    # Sort sections by token count (descending) and take top 200
    all_sections.sort(key=lambda x: x['token_count'], reverse=True)
    top_sections_tokens = all_sections[:200]
    
    # Write to CSV
    csv_output_file = 'sections_with_most_lines.csv'
    with open(csv_output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['doc_name', 'section_name', 'number_of_lines']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for section in top_sections_lines:
            writer.writerow({
                'doc_name': section['doc_name'],
                'section_name': section['section_name'],
                'number_of_lines': section['line_count']
            })
    
    # Write to Markdown for lines
    md_output_file = 'sections_with_most_lines.md'
    write_markdown_report(top_sections_lines, md_output_file)
    
    # Write to Markdown for characters
    md_chars_output_file = 'sections_with_most_characters.md'
    write_character_markdown_report(top_sections_chars, md_chars_output_file)
    
    # Write to Markdown for tokens
    md_tokens_output_file = 'sections_with_most_tokens.md'
    write_token_markdown_report(top_sections_tokens, md_tokens_output_file)
    
    print(f"CSV report generated: {csv_output_file}")
    print(f"Markdown report generated: {md_output_file}")
    print(f"Character count markdown report generated: {md_chars_output_file}")
    print(f"Token count markdown report generated: {md_tokens_output_file}")
    print(f"Total sections processed: {len(all_sections)}")
    print(f"Top {len(top_sections_lines)} sections written to CSV and line count Markdown")
    print(f"Top {len(top_sections_chars)} sections written to character count Markdown")
    print(f"Top {len(top_sections_tokens)} sections written to token count Markdown")
    
    if top_sections_lines:
        print(f"Top section by lines: '{top_sections_lines[0]['section_name']}' in '{top_sections_lines[0]['doc_name']}' with {top_sections_lines[0]['line_count']} lines")
    
    if top_sections_chars:
        print(f"Top section by characters: '{top_sections_chars[0]['section_name']}' in '{top_sections_chars[0]['doc_name']}' with {top_sections_chars[0]['char_count']} characters")
    
    if top_sections_tokens:
        print(f"Top section by tokens: '{top_sections_tokens[0]['section_name']}' in '{top_sections_tokens[0]['doc_name']}' with {top_sections_tokens[0]['token_count']} tokens")

if __name__ == "__main__":
    main()