import numpy as np

from abcg_controller.crowd import HeterogeneityConfig, sample_heterogeneity


def test_heterogeneity_is_deterministic_and_bounded() -> None:
    cfg = HeterogeneityConfig()
    first = sample_heterogeneity(80, seed=7, config=cfg)
    second = sample_heterogeneity(80, seed=7, config=cfg)

    assert np.allclose(first.radius, second.radius)
    assert np.allclose(first.preferred_speed, second.preferred_speed)
    assert np.allclose(first.time_gap, second.time_gap)

    assert np.all((first.radius >= cfg.radius_min) & (first.radius <= cfg.radius_max))
    assert np.all(
        (first.preferred_speed >= cfg.preferred_speed_min)
        & (first.preferred_speed <= cfg.preferred_speed_max)
    )
    assert np.all((first.time_gap >= cfg.time_gap_min) & (first.time_gap <= cfg.time_gap_max))


def test_disabled_heterogeneity_returns_means() -> None:
    cfg = HeterogeneityConfig(enabled=False)
    attributes = sample_heterogeneity(5, seed=123, config=cfg)
    assert np.allclose(attributes.radius, cfg.radius_mean)
    assert np.allclose(attributes.preferred_speed, cfg.preferred_speed_mean)
    assert np.allclose(attributes.time_gap, cfg.time_gap_mean)
