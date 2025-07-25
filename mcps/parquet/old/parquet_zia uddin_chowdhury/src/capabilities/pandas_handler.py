import pandas as pd
import asyncio
from concurrent.futures import ThreadPoolExecutor

# function to analyze csv file asynchronously
async def analyze_csv(file_path: str, column: str, threshold: int):
    """
    analyze csv file and filter rows based on column value
    returns: filtered dataframe as dict
    """
    try:
        # use thread pool for file I/O operations
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            df = await loop.run_in_executor(pool, pd.read_csv, file_path)
            
            filtered_df = await loop.run_in_executor(
                pool,
                lambda: df[df[column] > threshold]
            )
            
            # convert filtered dataframe to dict for json response
            result = filtered_df.to_dict(orient='records')
            
            return {
                "status": "success",
                "total_rows": len(df),
                "filtered_rows": len(filtered_df),
                "data": result
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"error processing csv: {str(e)}"
        } 