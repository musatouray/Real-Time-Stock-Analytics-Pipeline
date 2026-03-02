FROM python:3.11-slim

WORKDIR /usr/app/dbt

RUN pip install --no-cache-dir \
    dbt-core==1.8.2 \
    dbt-snowflake==1.8.2

COPY . .

RUN dbt deps --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt

CMD ["tail", "-f", "/dev/null"]
