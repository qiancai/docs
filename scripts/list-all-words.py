import os
import re
import csv
from collections import Counter
import argparse

target_doc_path = "/Users/grcai/Documents/GitHub/docs"

def extract_words_from_markdown(file_path):
    """Extract all words from a markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Remove markdown syntax (headers, links, code blocks, etc.)
        # Remove code blocks (```...```)
        content = re.sub(r'```[\s\S]*?```', '', content)
        # Remove inline code (`...`)
        content = re.sub(r'`[^`]*`', '', content)
        # Remove links [text](url)
        content = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', content)
        # Remove image links ![alt](url)
        content = re.sub(r'!\[([^\]]*)\]\([^\)]*\)', r'\1', content)
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        # Remove markdown headers (#, ##, etc.)
        content = re.sub(r'^#{1,6}\s*', '', content, flags=re.MULTILINE)
        # Remove emphasis markers (*, _, etc.)
        content = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', content)
        
        # Extract words (alphanumeric sequences, including words with hyphens)
        words = re.findall(r'\b[a-zA-Z]+(?:-[a-zA-Z]+)*\b', content.lower())
        
        return words
    
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []

def find_all_markdown_files(root_path):
    """Find all .md files in the directory tree."""
    markdown_files = []
    for root, dirs, files in os.walk(root_path):
        for file in files:
            if file.endswith('.md'):
                markdown_files.append(os.path.join(root, file))
    return markdown_files

def main():
    parser = argparse.ArgumentParser(description='Extract all words from markdown files and output to CSV')
    parser.add_argument('--output', '-o', default='word_counts.csv', 
                       help='Output CSV file name (default: word_counts.csv)')
    parser.add_argument('--min-count', '-m', type=int, default=1,
                       help='Minimum word count to include in output (default: 1)')
    
    args = parser.parse_args()
    
    print(f"Scanning markdown files in: {target_doc_path}")
    
    # Find all markdown files
    markdown_files = find_all_markdown_files(target_doc_path)
    print(f"Found {len(markdown_files)} markdown files")
    
    # Extract words from all files
    all_words = []
    processed_files = 0
    
    for file_path in markdown_files:
        words = extract_words_from_markdown(file_path)
        all_words.extend(words)
        processed_files += 1
        
        if processed_files % 50 == 0:
            print(f"Processed {processed_files}/{len(markdown_files)} files...")
    
    print(f"Finished processing {processed_files} files")
    
    # Count word frequencies
    word_counts = Counter(all_words)
    
    # Filter by minimum count
    filtered_words = {word: count for word, count in word_counts.items() 
                     if count >= args.min_count}
    
    print(f"Found {len(word_counts)} unique words total")
    print(f"Found {len(filtered_words)} unique words with count >= {args.min_count}")
    
    # Sort by frequency (descending)
    sorted_words = sorted(filtered_words.items(), key=lambda x: x[1], reverse=True)
    
    # Write to CSV
    output_path = os.path.join(os.path.dirname(target_doc_path), args.output)
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Word', 'Count'])  # Header
        writer.writerows(sorted_words)
    
    print(f"Word counts saved to: {output_path}")
    print(f"Top 10 most frequent words:")
    for word, count in sorted_words[:10]:
        print(f"  {word}: {count}")

if __name__ == "__main__":
    main()