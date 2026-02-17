# Uber Data Managment System

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