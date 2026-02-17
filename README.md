# Uber Data Managment System

## The EDA Section
For gainging a better understanding of the data before doing any coding, a simple EDA has been perfomer.  
This EDA is available [here](./notebooks/Basic_Analysis.ipynb).
Details of the findings in this section can be read in the notebook itself.  
However some key notes for desigining the reset of the system needs emphasizing:
- The dataset is NOT clean.
- The dataset does not have a unique identifier.
- Combination of some fields (like creating a timestamp) is possible.
- There are various `null` values present in the dataset which is semanticaly correct but dirty.
- The `null` values are represented by the string __null__ and not an empty space. 

## The Medalion Architecture
For the database, I choosed DuckDB because it is localized (meaning no seperate process needs to be running) and it can be integrated with Python seamlessly.
I used DBT to create the medalion architecture as I had experience of using it before.  
DBT [some explaination tops one paragraph about what DBT is].
The dataset will be imported AS IS using the __seed__ mechanisim that DBT provides for us.  
This seed will be recognized as the firs __Bronze__ layer.
#### The controversial Choice
For the next __Silver__ layer, what I did differs from what it is asked for in the project description. The implemented __Silver__ layer, is a clean version of the __Bronze__ layer imported as raw CSV file.  
The table __TransactionFact__ holds all the records from the original dataset with the addition of the following:
- Primary key is defined on it as the combination (concatenation) of __CustomerID__ and __BookingID__.
- Timestamp is created using a combination of Date and Time column and the coresponding columns are droped.
- The _one hot encoding_ feature types for cancelation is droped (as it can be easly recreated with a simple query).
- The reasons for cancelation are combined into one column.
This choice is because that the comman desing of the mdealion architecture follows the bellow pattern:
- Bronze: Raw data
- Silver: Cleaned Data with structured Schema
- Gold: Insight tables for better undestanding the business.

#### The Gold Layer
Usually the gold layer holds data for gaining easy access to data with business insights. But since the dataset is small here, we just seperated the Request table (which holds all the rides which was canceled) and Travels table (all compleeted rides).

### The Choice of Columns 
- Timestamp was created because holding Time and Date in seperate columns creates no real value for us and it increases the overhead as TIME and DATE are instances of Timestamps in many databases. So, instead of using two timestamps, we combined it into one.
  - Later on, the DATE section and the TIME section can be truncated simply using SQL commands.
- As I mentioned before, the `one-hot-encoding` columns which hold the cancelation type is again an overhead and can be removed easily. No real value here.  
- 
#### About the `null` values in the dataset.
When analyzed, we saw that many `null` values hold semantic and logical meaning. For example, when a ride is canceled, there is no meaning for __Driver Rating__ or __Payment Method__ as they are entities related to a ride that is completed.  
Most of the null values within the dataset fall under this category.
- One solution to mitigate the excess of null values is the same solution that we implemented for the gold layer. That is __Sperate the entites of Travel and Requests__. This removes many instances of null values related to the __Request__ entity as some of the columns holds almost no meaning to this table.
- The same goes for the `Customer Rating` and `Driver Rating` columns. They are mostly empty when there is an uncompleted ride. So again, these null values do not mean __Curopted Data__. Its just a logical consequence of business logic.
- Customer Rating and Driver Rating is only relavent to `Travels` table. Hence, it can be removed from the `Requests` table.
  
## The CRUD API
Using FastAPI we created a CRUD endpoint. This endpoint is present under `/api/v1` end point and it includes direct HTTP methods.
- Main endpoint is `/api/v1/transactions`
- Methods that can be used are:
  - GET for Read operation
  - POST for Create operation
  - PATCH for Update operation
  - DELETE for Delete operation
- Documents are avilable at `/docs`

Some important notes:
- The Booking ID is created automaticaly with a random function each time a create request is sent.
- The unique identifier in the database are: CustomerID + BookingID. So this is needed for Update, Delete and Read requests.
- When a new record is to be created, some values are mandetory and some are optional (avilable in docs).
- Tests has been written and can be ran using the following commands:
  - `poetry run pytest tests/test_transaction_sequential.py`

## Commands
### Important DBT Commands (DuckDB Project)

#### Create New Project
```bash
dbt init project_name
```

#### Configure `profiles.yml`

```yml
project_name:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: /absolute/path/to/db/project_name.duckdb
      threads: 1
```

#### Test Connection

```bash
dbt debug
```

#### Run all seeds

```bash
dbt seed
```

#### Force overwrite seed tables

```bash
dbt seed --full-refresh
```

#### Run specific seed

```bash
dbt seed --select transactions
```

#### Run specific model

```bash
dbt run --select silver.transaction_fact
dbt run --select gold.travels
dbt run --select gold.requests
```

#### Run entire layer

```bash
dbt run --select silver
dbt run --select gold
```

#### Build (Recommended Command)

Build runs:

* seeds
* models
* tests

##### Run everything

```bash
dbt build
```

##### Full refresh everything

```bash
dbt build --full-refresh
```

---

#### Run all tests

```bash
dbt test
```

#### Run tests for specific model

```bash
dbt test --select gold.travels
```

#### Generate docs

```bash
dbt docs generate
```

#### Serve docs locally

```bash
dbt docs serve
```

### Remove compiled artifacts

```bash
dbt clean
```

#### Remove DuckDB warehouse (true reset)

```bash
rm db/analytics.duckdb
```

#### Full clean rebuild (recommended)

```bash
rm db/analytics.duckdb
dbt clean
dbt build --full-refresh
```

#### Install packages

```bash
dbt deps
```

#### List all models/seeds/tests

```bash
dbt ls
```

#### List only models

```bash
dbt ls --resource-type model
```

#### Run downstream models

```bash
dbt run --select silver.transaction_fact+
```

#### Run model and its parents

```bash
dbt run --select +gold.travels
```

#### Run entire lineage

```bash
dbt run --select +gold.travels+
```


### Poetry – Environment & Dependency Management

#### Install dependencies

```bash
poetry install
```

Creates virtual environment and installs everything from `pyproject.toml`.

#### Activate virtual environment (optional)

```bash
poetry shell
```

Exit:

```bash
exit
```

> You don’t need to activate it if you use `poetry run`.

#### Add new dependency

```bash
poetry add <package-name>
```

Example:

```bash
poetry add fastapi
```

#### Add dev dependency

```bash
poetry add --group dev pytest
```

#### Remove dependency

```bash
poetry remove <package-name>
```

#### Run any command inside Poetry environment

```bash
poetry run <command>
```

Example:

```bash
poetry run python script.py
```

#### Rebuild dbt warehouse from scratch

```bash
rm db/analytics.duckdb
poetry run dbt build --full-refresh
```

---

### Run FastAPI (Uvicorn)

Assume app entrypoint:

```
src/main.py
```

and inside it:

```python
app = FastAPI()
```

#### Run in development mode

```bash
poetry run uvicorn src.main:app --reload
```

Explanation:

* `src.main` → module path
* `app` → FastAPI instance
* `--reload` → auto reload on file change

#### Run on custom host/port

```bash
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### Run Streamlit Dashboard

Assume dashboard file:

```
app/dashboard.py
```

Run:

```bash
poetry run streamlit run app/dashboard.py
```

Streamlit will show:

```
Local URL: http://localhost:8501
```

Open that in browser.


#### Run on specific port

```bash
poetry run streamlit run app/dashboard.py --server.port 8502
```