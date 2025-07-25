# function to sort log entries by timestamp
def sort_log_by_timestamp(file_path: str):
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # sort lines based on timestamp
        sorted_lines = sorted(lines, key=lambda line: line.split()[0] + " " + line.split()[1])
        return sorted_lines
    except Exception as e:
        return {"error": f"error processing file: {str(e)}"} 