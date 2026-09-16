import numpy as np

from scene import BoundaryOpening, RectangularScenario


def test_square_closed_contract() -> None:
    scenario = RectangularScenario.square(12.0)
    assert scenario.closed
    assert scenario.step1_contract_valid()
    assert np.allclose(
        scenario.boundary_vertices(),
        np.array([[0.0, 0.0], [12.0, 0.0], [12.0, 12.0], [0.0, 12.0]]),
    )
    assert scenario.contains(np.array([[6.0, 6.0], [0.0, 0.0]])).tolist() == [True, True]


def test_rectangle_closed_contract() -> None:
    scenario = RectangularScenario.rectangle(16.0, 10.0)
    assert scenario.closed
    assert scenario.step1_contract_valid()
    mask = scenario.contains(np.array([[8.0, 5.0], [16.1, 5.0]]), margin=0.2)
    assert mask.tolist() == [True, False]


def test_future_opening_is_not_step1_valid() -> None:
    scenario = RectangularScenario(
        name="rectangle_with_exit",
        width=16.0,
        height=10.0,
        kind="rectangle",
        openings=(BoundaryOpening(wall="right", start=4.0, end=6.0),),
    )
    assert not scenario.closed
    assert not scenario.step1_contract_valid()
