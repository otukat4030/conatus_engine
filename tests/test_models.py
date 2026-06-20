from conatus_engine.models import Affect, Encounter, Mode, Person, evaluate_encounter


def test_power_increase_is_joy_and_active_when_cause_is_sufficient() -> None:
    person = Person(name="Spinoza", power=10.0)
    encounter = Encounter(
        description="友人との対話",
        power_delta=2.5,
        sufficient_cause=True,
    )

    result = evaluate_encounter(person, encounter)

    assert result.after_power == 12.5
    assert result.affect is Affect.JOY
    assert result.mode is Mode.ACTIVE


def test_power_decrease_is_sadness_and_passive_when_cause_is_insufficient() -> None:
    person = Person(name="Student", power=8.0)
    encounter = Encounter(
        description="理由のわからない不安",
        power_delta=-3.0,
        sufficient_cause=False,
    )

    result = evaluate_encounter(person, encounter)

    assert result.after_power == 5.0
    assert result.affect is Affect.SADNESS
    assert result.mode is Mode.PASSIVE


def test_no_power_change_is_neutral() -> None:
    person = Person(name="Reader", power=4.0)
    encounter = Encounter(
        description="静かな読書",
        power_delta=0.0,
        sufficient_cause=True,
    )

    result = evaluate_encounter(person, encounter)

    assert result.after_power == 4.0
    assert result.affect is Affect.NEUTRAL
