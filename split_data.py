import json
import os

def split_enhanced_data():
    print("Loading original data...")
    with open('enhanced_ace_crash_data.json', 'r') as f:
        data = json.load(f)
    
    # Option 1: Split by data type
    file1_data = {
        'crash_data': data['crash_data'],
        'ace_data': data['ace_data']
    }
    
    file2_data = {
        'transit_data': data['transit_data']
    }
    
    # Save split files
    print("Saving split files...")
    with open('data_part1.json', 'w') as f:
        json.dump(file1_data, f, separators=(',', ':'))
    
    with open('data_part2.json', 'w') as f:
        json.dump(file2_data, f, separators=(',', ':'))
    
    # Check file sizes
    original_size = os.path.getsize('enhanced_ace_crash_data.json')
    part1_size = os.path.getsize('data_part1.json')
    part2_size = os.path.getsize('data_part2.json')
    
    print(f"Original file: {original_size:,} bytes ({original_size/1024/1024:.1f} MB)")
    print(f"Part 1 (crash+ace): {part1_size:,} bytes ({part1_size/1024/1024:.1f} MB)")
    print(f"Part 2 (transit): {part2_size:,} bytes ({part2_size/1024/1024:.1f} MB)")
    print(f"Total split: {(part1_size + part2_size):,} bytes")
    
    return part1_size, part2_size

if __name__ == "__main__":
    split_enhanced_data()