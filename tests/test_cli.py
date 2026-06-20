from conatus_engine.cli import main


def test_main_applies_multiple_events(monkeypatch, capsys) -> None:
    inputs = iter(
        [
            "Spinoza",
            "10",
            "y",
            "event-1",
            "first event",
            "2",
            "y",
            "y",
            "y",
            "event-2",
            "second event",
            "-3",
            "n",
            "y",
            "n",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    main()

    output = capsys.readouterr().out

    assert "更新前の力能: 10.0" in output
    assert "更新後の力能: 12.0" in output
    assert "更新前の力能: 12.0" in output
    assert "更新後の力能: 9.0" in output
    assert "力能: 9.0" in output
