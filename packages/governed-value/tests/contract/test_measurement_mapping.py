from governed_value.domain.enums import (
    OUTCOME_MEASUREMENT,
    MeasurementMethod,
    OutcomeClass,
)


def test_every_outcome_class_maps_to_exactly_one_method():
    assert set(OUTCOME_MEASUREMENT) == set(OutcomeClass)
    assert OUTCOME_MEASUREMENT[OutcomeClass.DETERMINISTIC_AUTOMATION] is (
        MeasurementMethod.BEFORE_AFTER_BASELINE
    )
    assert OUTCOME_MEASUREMENT[OutcomeClass.JUDGMENT_SUPPORT] is (
        MeasurementMethod.HOLDOUT_OR_STAGED
    )
    assert OUTCOME_MEASUREMENT[OutcomeClass.DISCOVERY_INSIGHT] is (
        MeasurementMethod.OPTION_VALUE
    )
    assert OUTCOME_MEASUREMENT[OutcomeClass.RISK_CONTAINMENT] is (
        MeasurementMethod.ACTUARIAL_BASELINE
    )
