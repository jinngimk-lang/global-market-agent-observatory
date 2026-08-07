from app.research.volume_profile import VolumeNode, build_volume_profile


def test_volume_profile_finds_poc():
    result = build_volume_profile(
        [
            VolumeNode(100, 10),
            VolumeNode(101, 50),
            VolumeNode(102, 20),
        ]
    )

    assert result.poc == 101
    assert result.value_area_low == 100
    assert result.value_area_high == 102


def test_empty_volume_profile_is_safe():
    result = build_volume_profile([])
    assert result.poc is None
    assert result.nodes == ()
