from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app


def test_validate_config_command_succeeds() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-config", "--config", "configs/baseline.yaml"])

    assert result.exit_code == 0
    assert "Validated short-rate-anomaly-regimes in strict mode" in result.stdout


def test_validate_data_command_succeeds() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-data", "--registry", "configs/data_sources.yaml"])

    assert result.exit_code == 0
    assert "registered sources" in result.stdout


def test_show_milestones_command_lists_release_gate() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["show-milestones"])

    assert result.exit_code == 0
    assert "Evidence freeze" in result.stdout
    assert "Adversarial audit and release" in result.stdout


def test_milestone_gated_cli_commands_report_not_implemented() -> None:
    runner = CliRunner()
    command_arguments = [
        ["estimate-rate-innovation", "--config", "configs/baseline.yaml"],
        ["run-baseline", "--config", "configs/baseline.yaml"],
        ["run-regimes", "--config", "configs/regimes.yaml"],
        ["build-report", "--config", "configs/reporting.yaml"],
    ]

    for arguments in command_arguments:
        result = runner.invoke(app, arguments)

        assert result.exit_code == 1
        assert isinstance(result.exception, NotImplementedError)
