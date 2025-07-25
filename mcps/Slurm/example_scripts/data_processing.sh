#!/bin/bash
#SBATCH --job-name=data_processing
#SBATCH --output=logs/slurm_output/slurm_%j.out
#SBATCH --error=logs/slurm_output/slurm_%j.err
#SBATCH --time=00:15:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8GB
#SBATCH --partition=compute

echo "=== Data Processing Job ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Start Time: $(date)"
echo "Node: $(hostname)"
echo "CPUs allocated: $SLURM_CPUS_ON_NODE"
echo ""

# Create directories for data processing
mkdir -p data_input data_output logs

echo "📊 Generating sample dataset..."
# Create sample data files
for i in {1..5}; do
    data_file="data_input/dataset_${i}.csv"
    echo "Creating $data_file..."
    
    # Generate CSV header
    echo "id,value,timestamp,category" > $data_file
    
    # Generate sample data
    for j in {1..100}; do
        id=$((i * 100 + j))
        value=$(echo "scale=2; $RANDOM / 100" | bc -l)
        timestamp=$(date +%s)
        category="cat_$((j % 5 + 1))"
        echo "$id,$value,$timestamp,$category" >> $data_file
    done
done

echo "✅ Sample data generated!"
echo ""

# Process each data file
echo "🔄 Processing data files..."
for input_file in data_input/*.csv; do
    filename=$(basename "$input_file" .csv)
    output_file="data_output/processed_${filename}.txt"
    
    echo "Processing: $input_file -> $output_file"
    
    # Create processing script
    cat > process_data.py << 'EOF'
import sys
import csv
from collections import defaultdict

input_file = sys.argv[1]
output_file = sys.argv[2]

print(f"Reading data from: {input_file}")

# Process CSV data
data = defaultdict(list)
total_value = 0
count = 0

try:
    with open(input_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = row['category']
            value = float(row['value'])
            data[category].append(value)
            total_value += value
            count += 1

    # Generate summary
    with open(output_file, 'w') as f:
        f.write(f"Data Processing Summary\n")
        f.write(f"======================\n")
        f.write(f"Input file: {input_file}\n")
        f.write(f"Total records: {count}\n")
        f.write(f"Average value: {total_value/count:.2f}\n\n")
        
        f.write("Category Analysis:\n")
        for category, values in data.items():
            avg_val = sum(values) / len(values)
            f.write(f"  {category}: {len(values)} records, avg = {avg_val:.2f}\n")

    print(f"Results written to: {output_file}")
    
except Exception as e:
    print(f"Error processing {input_file}: {e}")
    with open(output_file, 'w') as f:
        f.write(f"ERROR: Failed to process {input_file}\n")
        f.write(f"Error: {e}\n")
EOF

    # Run processing script
    python3 process_data.py "$input_file" "$output_file"
    
    echo "  ✅ Completed: $filename"
done

# Clean up processing script
rm -f process_data.py

echo ""
echo "📈 Generating final summary report..."

# Create final summary
summary_file="data_output/FINAL_SUMMARY.txt"
echo "Data Processing Job Summary" > $summary_file
echo "===========================" >> $summary_file
echo "Job ID: $SLURM_JOB_ID" >> $summary_file
echo "Processed at: $(date)" >> $summary_file
echo "Node: $(hostname)" >> $summary_file
echo "" >> $summary_file

echo "Files processed:" >> $summary_file
ls -la data_input/*.csv >> $summary_file
echo "" >> $summary_file

echo "Output files generated:" >> $summary_file
ls -la data_output/ >> $summary_file

echo "✅ Data processing completed!"
echo ""
echo "📁 Results available in:"
echo "  - Individual results: data_output/processed_*.txt"
echo "  - Summary report: $summary_file"

echo ""
echo "📋 Quick summary:"
cat $summary_file

echo ""
echo "Job completed at: $(date)"
echo "=== End of Data Processing Job ==="
