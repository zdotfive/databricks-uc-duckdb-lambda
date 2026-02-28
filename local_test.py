import time

from uc_reader import _get_temp_credentials, read_uc_table


def local_test(table: str, filters: str | None = None, limit: int = 10) -> None:
    SEP = "-" * 60

    print(f"\n{SEP}")
    print(f"  Tabella : {table}")
    print(f"  Filters : {filters or '—'}")
    print(f"  Limit   : {limit}")
    print(SEP)

    t_total = time.perf_counter()

    print("\n[1/2] Richiedo credenziali temporanee S3 a Unity Catalog...")
    t0 = time.perf_counter()
    s3_url, aws_creds = _get_temp_credentials(table)
    t_creds = time.perf_counter() - t0
    print(f"  s3_url     : {s3_url}")
    print(f"  access_key : {aws_creds['access_key_id'][:8]}***")
    print(f"  tempo      : {t_creds:.3f}s")

    print("\n[2/2] Leggo la tabella Delta con DuckDB → PyArrow...")
    t0 = time.perf_counter()
    arrow_table = read_uc_table(table, filters=filters, limit=limit)
    t_query = time.perf_counter() - t0
    print(f"  tempo      : {t_query:.3f}s")

    print(f"\n  Righe   : {arrow_table.num_rows}")
    print(f"  Colonne : {arrow_table.num_columns}")

    t_total = time.perf_counter() - t_total
    print(f"\n  Tempi:")
    print(f"    UC credential vending : {t_creds:.3f}s")
    print(f"    DuckDB query + fetch  : {t_query:.3f}s")
    print(f"    Totale                : {t_total:.3f}s")
    print(f"\n{SEP}\n")


if __name__ == "__main__":
    local_test(
        table="labs.duckdb_uc_test.first_table_iceberg",
        filters="age = 30",
        limit=10,
    )
