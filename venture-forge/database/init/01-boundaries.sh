#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v product_password="$PRODUCT_DB_PASSWORD" -v company_password="$COMPANY_DB_PASSWORD" <<'SQL'
CREATE ROLE vf_product LOGIN PASSWORD :'product_password';
CREATE ROLE vf_company LOGIN PASSWORD :'company_password';
CREATE DATABASE vf_product OWNER vf_product;
CREATE DATABASE vf_product_test OWNER vf_product;
CREATE DATABASE vf_company OWNER vf_company;
REVOKE CONNECT ON DATABASE vf_product FROM PUBLIC;
REVOKE CONNECT ON DATABASE vf_product_test FROM PUBLIC;
REVOKE CONNECT ON DATABASE vf_company FROM PUBLIC;
GRANT CONNECT ON DATABASE vf_product TO vf_product;
GRANT CONNECT ON DATABASE vf_product_test TO vf_product;
GRANT CONNECT ON DATABASE vf_company TO vf_company;
SQL
