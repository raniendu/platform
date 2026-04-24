"""
Property-based tests for configuration module.

**Feature: prefect-digitalocean-deployment, Property 10: Configuration environment switching**

Tests that configuration serialization and deserialization produces equivalent objects,
ensuring consistent format across all configuration files.

**Validates: Requirements 8.5**
"""

from hypothesis import given, settings, strategies as st

from config.settings import (
    DatabaseConfig,
    Environment,
    EnvironmentConfig,
    PrefectConfig,
)


# Strategies for generating valid configuration values
prefect_config_strategy = st.builds(
    PrefectConfig,
    api_url=st.text(min_size=1, max_size=100).map(lambda s: f"http://{s.replace(' ', '')}/api"),
    ui_url=st.text(min_size=1, max_size=100).map(lambda s: f"http://{s.replace(' ', '')}"),
)

database_config_strategy = st.builds(
    DatabaseConfig,
    host=st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
    port=st.integers(min_value=1, max_value=65535),
    name=st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
    user=st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
    password=st.text(min_size=0, max_size=100),
)

environment_config_strategy = st.builds(
    EnvironmentConfig,
    environment=st.sampled_from([Environment.LOCAL, Environment.PRODUCTION]),
    prefect=prefect_config_strategy,
    database=database_config_strategy,
    domain=st.one_of(st.none(), st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != "")),
)


@given(config=environment_config_strategy)
@settings(max_examples=100)
def test_config_round_trip_json(config: EnvironmentConfig) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 10: Configuration environment switching**
    
    Property: For any valid EnvironmentConfig, serializing to JSON then deserializing
    should produce an equivalent configuration object.
    
    This ensures configuration can be safely stored and loaded from JSON files
    with consistent format across all configuration files.
    
    **Validates: Requirements 8.5**
    """
    # Serialize to JSON
    json_str = config.model_dump_json()
    
    # Deserialize from JSON
    restored_config = EnvironmentConfig.model_validate_json(json_str)
    
    # Verify equivalence
    assert restored_config == config, (
        f"Round-trip failed:\n"
        f"Original: {config}\n"
        f"Restored: {restored_config}"
    )


@given(config=environment_config_strategy)
@settings(max_examples=100)
def test_config_round_trip_dict(config: EnvironmentConfig) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 10: Configuration environment switching**
    
    Property: For any valid EnvironmentConfig, serializing to dict then deserializing
    should produce an equivalent configuration object.
    
    This ensures configuration can be safely converted to/from dictionaries
    for programmatic manipulation.
    
    **Validates: Requirements 8.5**
    """
    # Serialize to dict
    config_dict = config.model_dump()
    
    # Deserialize from dict
    restored_config = EnvironmentConfig.model_validate(config_dict)
    
    # Verify equivalence
    assert restored_config == config, (
        f"Round-trip failed:\n"
        f"Original: {config}\n"
        f"Restored: {restored_config}"
    )


@given(prefect_config=prefect_config_strategy)
@settings(max_examples=100)
def test_prefect_config_round_trip(prefect_config: PrefectConfig) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 10: Configuration environment switching**
    
    Property: For any valid PrefectConfig, serializing then deserializing
    should produce an equivalent configuration object.
    
    **Validates: Requirements 8.5**
    """
    json_str = prefect_config.model_dump_json()
    restored = PrefectConfig.model_validate_json(json_str)
    assert restored == prefect_config


@given(db_config=database_config_strategy)
@settings(max_examples=100)
def test_database_config_round_trip(db_config: DatabaseConfig) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 10: Configuration environment switching**
    
    Property: For any valid DatabaseConfig, serializing then deserializing
    should produce an equivalent configuration object.
    
    **Validates: Requirements 8.5**
    """
    json_str = db_config.model_dump_json()
    restored = DatabaseConfig.model_validate_json(json_str)
    assert restored == db_config
