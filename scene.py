"""Scene construction. Add future geometry builders to SCENES."""
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon


@dataclass(frozen=True)
class Scene:
    name: str
    width: float
    height: float
    openings: tuple = ()

    @property
    def size(self):
        return np.array([self.width, self.height])

    @property
    def polygon(self):
        return Polygon([(0, 0), (self.width, 0), (self.width, self.height), (0, self.height)])


def rectangle(config):
    width, height = float(config['width']), float(config['height'])
    if not np.isfinite([width, height]).all() or min(width, height) <= 0:
        raise ValueError('Scene dimensions must be finite and positive')
    if config.get('openings') != []:
        raise ValueError('Step 1 requires closed scenes: openings: []')
    return Scene(config['type'], width, height)


def square(config):
    result = rectangle(config)
    if not np.isclose(result.width, result.height):
        raise ValueError('Square requires width == height')
    return result


SCENES = {'square': square, 'rectangle': rectangle}


def build_scene(config):
    if config['type'] not in SCENES:
        raise ValueError(f"Unsupported scene type: {config['type']}")
    return SCENES[config['type']](config)
