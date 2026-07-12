from work_frontier import hello_contract


def test_hello_contract_when_bootstrap_package_imported() -> None:
    # Given the installed standalone package
    # When its baseline contract is requested
    result = hello_contract()

    # Then it identifies Work Frontier
    assert result == "work-frontier"
