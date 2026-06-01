"""Smoke tests for jasentool.config (per-profile expected-output schedule)."""

import pytest

from jasentool.config import PROFILES, get_profile


PROFILE_KEYS = {"profile", "species", "species_full", "outputs"}
OUTPUT_KEYS = {"software_name", "dirname", "mask", "file_ext"}


def test_profiles_have_required_keys():
    assert len(PROFILES) == 5
    for entry in PROFILES:
        assert PROFILE_KEYS.issubset(entry.keys())
        assert isinstance(entry["outputs"], list)
        assert entry["outputs"], f"{entry['profile']} has no outputs"


def test_output_entries_have_required_keys():
    for profile in PROFILES:
        for output in profile["outputs"]:
            missing = OUTPUT_KEYS - output.keys()
            assert not missing, (
                f"{profile['profile']}/{output.get('software_name')} missing {missing}"
            )


def test_known_profile_names():
    names = {p["profile"] for p in PROFILES}
    assert names == {
        "staphylococcus_aureus",
        "escherichia_coli",
        "mycobacterium_tuberculosis",
        "streptococcus_pyogenes",
        "streptococcus",
    }


def test_get_profile_returns_matching_entry():
    entry = get_profile("staphylococcus_aureus")
    assert entry["species"] == "saureus"
    assert any(o["software_name"] == "sccmec" for o in entry["outputs"])


def test_get_profile_raises_on_unknown():
    with pytest.raises(KeyError) as excinfo:
        get_profile("bogus")
    assert "bogus" in str(excinfo.value)


def test_tb_profile_omits_non_tb_tools():
    tb = get_profile("mycobacterium_tuberculosis")
    software = {o["software_name"] for o in tb["outputs"]}
    assert "resfinder_json" not in software
    assert "mlst_tsv" not in software
    assert "mykrobe" in software
    assert "tbprofiler_json" in software


def test_file_ext_can_be_str_or_list():
    """`file_ext` is allowed to be a single extension or a list of allowed extensions."""
    for profile in PROFILES:
        for output in profile["outputs"]:
            assert isinstance(output["file_ext"], (str, list)), (
                f"{profile['profile']}/{output['software_name']} has invalid "
                f"file_ext type: {type(output['file_ext']).__name__}"
            )


def test_ecoli_profile_includes_ecoli_specific_tools():
    ecoli = get_profile("escherichia_coli")
    software = {o["software_name"] for o in ecoli["outputs"]}
    assert "shigatyper" in software
    assert "serotypefinder_json" in software
