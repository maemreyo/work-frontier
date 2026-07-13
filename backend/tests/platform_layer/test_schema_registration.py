from work_frontier.platform.persistence.schema import metadata


def test_schema_registers_each_table_name_once() -> None:
    table_names = tuple(metadata.tables)
    assert len(table_names) == len(set(table_names))
    assert table_names.count("local_identities") == 1
