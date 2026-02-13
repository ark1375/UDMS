from IPython.display import display, Markdown
import pandas as pd

import pandas as pd

def profile_column(df: pd.DataFrame, col: str, sample_size: int = 5):
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found in DataFrame.")

    total_rows = len(df)
    series = df[col]

    null_count = series.isnull().sum()
    null_pct = round(series.isnull().mean() * 100, 2)
    dtype = series.dtype
    unique_count = series.nunique(dropna=True)

    duplicate_count = series.duplicated().sum()
    duplicate_pct = round((duplicate_count / total_rows) * 100, 2)

    memory_usage = series.memory_usage(deep=True)
    sample_values = series.dropna().unique()[:sample_size]

    # If duplicates > 98%, show all unique values (safe guard for large cardinality)
    show_all_uniques = duplicate_pct > 98 and unique_count <= 50
    
    if show_all_uniques:
        unique_values = series.dropna().unique()
        unique_section = f"""
#####
All Unique Values:
`{list(unique_values)}`
"""
    else:
        unique_section = ""

    return f"""
#### Column Profile: `{col}`  

##### Basic Info
- **Data Type:** `{dtype}`
- **Total Rows:** `{total_rows:,}`
- **Memory Usage:** `{memory_usage:,} bytes`
- **Null Count:** `{null_count:,}`
- **Null Percentage:** `{null_pct}%`
- **Unique Values:** `{unique_count:,}`
- **Duplicate Values:** `{duplicate_count:,}`
- **Duplicate Percentage:** `{duplicate_pct}%`

##### Sample Values
`{list(sample_values)}`

{unique_section}

---
"""
