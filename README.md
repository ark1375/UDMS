# Uber Data Managment System

## The EDA Section

For gaining a better understanding of the data before doing any coding, a simple EDA was performed.
This EDA is available [here](./notebooks/Basic_Analysis.ipynb).

Details of the findings in this section can be read in the notebook itself.
However, some key notes for designing the rest of the system need to be emphasized:

* The dataset is **not clean**.
* The dataset does **not** have a unique identifier.
* A combination of some fields (for example, creating a timestamp) is possible.
* There are various `null` values present in the dataset which are **semantically correct**, but still considered dirty.
* The `null` values are represented by the string **`null`**, not as actual SQL `NULL` values or empty fields.

---

## The Medalion Architecture

For the database, I chose **DuckDB** because it is localized (meaning no separate process needs to be running) and can be integrated with Python seamlessly.

I used **DBT** to create the medallion architecture, as I had prior experience using it.
DBT is a transformation framework that allows analytics engineers to define data transformations as code, enforce schemas, document models, and manage data pipelines directly within the data warehouse.

The dataset is imported **as-is** using the **seed** mechanism that DBT provides.
This seed is recognized as the first **Bronze** layer.

#### The controversial Choice

For the next **Silver** layer, the implementation differs slightly from what is asked for in the project description.

The implemented **Silver** layer is a cleaned and structured version of the **Bronze** layer, which was imported as a raw CSV file.
The table **`TransactionFact`** holds all records from the original dataset with the following additions and transformations:

* A primary key is defined as a combination (concatenation) of **CustomerID** and **BookingID**.
* A unified timestamp is created by combining the Date and Time columns, and the original columns are dropped.
* One-hot-encoded columns representing cancellation types are dropped, as they can be easily recreated using simple SQL queries.
* Cancellation reasons are consolidated into a single column.

This choice follows the commonly accepted medallion architecture pattern:

* **Bronze**: Raw data
* **Silver**: Cleaned data with a structured schema
* **Gold**: Aggregated or domain-specific tables for business understanding

---

#### The Gold Layer

Typically, the Gold layer holds data optimized for business insights and analytics.
However, since the dataset is relatively small, the Gold layer is implemented by separating the data into two domain-specific tables:

* **Requests**: Contains all rides that were canceled.
* **Travels**: Contains all completed rides.

This separation improves semantic clarity and reduces unnecessary null values.

---

### The Choice of Columns

* A unified timestamp was created because holding Date and Time in separate columns provides no real value and increases overhead. In many databases, DATE and TIME are already represented as parts of a TIMESTAMP.

  * When needed, the DATE or TIME components can easily be extracted using SQL functions.
* As mentioned earlier, one-hot-encoded cancellation-type columns introduce unnecessary overhead and can be reconstructed dynamically when required. They do not add meaningful long-term value and were therefore removed.

---

#### About the `null` values in the dataset.

During analysis, it became clear that many `null` values have semantic and logical meaning rather than indicating corrupted data.

For example, when a ride is canceled, fields such as **Driver Rating** or **Payment Method** are not applicable, as they only relate to completed rides.
Most null values in the dataset fall into this category.

* One approach to mitigating excessive null values is the same solution implemented in the Gold layer: **separating the entities of Travels and Requests**.
  This removes many null fields from the Requests table, where those attributes have no semantic meaning.
* The same logic applies to **Customer Rating** and **Driver Rating**, which are largely empty for uncompleted rides. These null values do not indicate bad data, but rather reflect valid business logic.
* Since Customer Rating and Driver Rating are only relevant for completed rides, they are retained exclusively in the **Travels** table and removed from **Requests**.

---

## The CRUD API

Using **FastAPI**, a CRUD API was implemented.
The API is available under the `/api/v1` endpoint and exposes standard HTTP methods.

* Main endpoint: `/api/v1/transactions`
* Supported methods:

  * **GET** for Read operations
  * **POST** for Create operations
  * **PATCH** for Update operations
  * **DELETE** for Delete operations
* Interactive API documentation is available at `/docs`

Some important notes:

* **BookingID** is generated automatically using a random function each time a create request is sent.
* The unique identifier in the database is a composite key: **CustomerID + BookingID**.
  This composite key is required for Read, Update, and Delete operations.
* When creating a new record, some fields are mandatory while others are optional. These constraints are documented in the API schema.
* Tests have been written and can be executed using the following command:

  * `poetry run pytest tests/test_transaction_sequential.py`
  * This test suite is **sequential**, meaning that operations are executed in a specific order and later assertions depend on the results of earlier operations.

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