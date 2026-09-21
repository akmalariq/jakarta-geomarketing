import h3
import pytest

from export.export_dashboard import wkt_to_coords

JAKARTA_CENTER = (-6.2, 106.8167)
RESOLUTION = 8


def test_latlng_to_cell_is_deterministic_and_valid():
    cell = h3.latlng_to_cell(*JAKARTA_CENTER, RESOLUTION)

    assert h3.is_valid_cell(cell)
    assert h3.get_resolution(cell) == RESOLUTION


def test_neighbouring_points_can_share_a_cell():
    cell_a = h3.latlng_to_cell(-6.2000, 106.8167, RESOLUTION)
    cell_b = h3.latlng_to_cell(-6.2001, 106.8168, RESOLUTION)

    assert cell_a == cell_b


def test_cell_resolution_eight_is_about_half_a_square_km():
    cell = h3.latlng_to_cell(*JAKARTA_CENTER, RESOLUTION)

    area = h3.cell_area(cell, unit="km^2")
    assert 0.6 < area < 0.9


def test_boundary_wkt_round_trips_into_a_closed_ring():
    cell = h3.latlng_to_cell(*JAKARTA_CENTER, RESOLUTION)
    vertexes = h3.cell_to_vertexes(cell)
    ring = [(lng, lat) for lat, lng in (h3.vertex_to_latlng(v) for v in vertexes)]
    closed = ring + [ring[0]]
    body = ", ".join(f"{lng:.6f} {lat:.6f}" for lng, lat in closed)
    wkt = f"POLYGON(({body}))"

    parsed = wkt_to_coords(wkt)

    assert len(parsed) == len(closed)
    assert parsed[0] == parsed[-1]
    assert all(106.5 < lng < 107.1 for lng, _ in parsed)
    assert all(-6.5 < lat < -5.9 for _, lat in parsed)


def test_wkt_to_coords_rejects_malformed_input():
    with pytest.raises(ValueError):
        wkt_to_coords("not a polygon")
