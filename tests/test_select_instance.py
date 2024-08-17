import pytest
from unittest import mock
from pylambdacloud.select_instance import (
    sort_by_price_fn,
    remove_non_available_instances,
    flatten_instance_information,
    list_instance_types,
    prompt_for_instance_type,
)


@pytest.fixture
def sample_instance_data():
    return {
        "gpu_1x_a100": {
            "instance_type": {
                "name": "gpu_1x_a100",
                "description": "1x RTX A100 (24 GB)",
                "price_cents_per_hour": "80",
                "specs": {
                    "vcpus": 24,
                    "memory_gib": 800,
                    "storage_gib": 512,
                },
            },
            "regions_with_capacity_available": [
                {"name": "us-tx-1", "description": "Austin, Texas"}
            ],
        },
        "gpu_4x_a6000": {
            "instance_type": {
                "name": "gpu_4x_a6000",
                "description": "4x RTX 6000 (24 GB)",
                "price_cents_per_hour": "110",
                "specs": {
                    "vcpus": 24,
                    "memory_gib": 800,
                    "storage_gib": 512,
                },
            },
            "regions_with_capacity_available": [
                {"name": "us-phoenix-1", "description": "Phoenix, Arizona"}
            ],
        },
        "gpu_8x_v100": {
            "instance_type": {
                "name": "gpu_8x_v100",
                "description": "8x RTX V100 (32 GB)",
                "price_cents_per_hour": "150",
                "specs": {
                    "vcpus": 32,
                    "memory_gib": 1024,
                    "storage_gib": 1024,
                },
            },
            "regions_with_capacity_available": [],
        },
    }


@pytest.fixture
def flattened_instance_data():
    return {
        "gpu_1x_a100": {
            "price_cents_per_hour": "80",
            "description": "1x RTX A100 (24 GB)",
            "specs": {"vcpus": 24, "memory_gib": 800, "storage_gib": 512},
            "regions_with_capacity_available": ["us-tx-1"],
        },
        "gpu_4x_a6000": {
            "price_cents_per_hour": "110",
            "description": "4x RTX 6000 (24 GB)",
            "specs": {"vcpus": 24, "memory_gib": 800, "storage_gib": 512},
            "regions_with_capacity_available": ["us-phoenix-1"],
        },
        "gpu_8x_v100": {
            "price_cents_per_hour": "150",
            "description": "8x RTX V100 (32 GB)",
            "specs": {"vcpus": 32, "memory_gib": 1024, "storage_gib": 1024},
            "regions_with_capacity_available": [],
        },
    }


def test_remove_non_available_instances(sample_instance_data):
    available_instances = remove_non_available_instances(sample_instance_data)
    assert "gpu_8x_v100" not in available_instances
    assert "gpu_1x_a100" in available_instances
    assert "gpu_4x_a6000" in available_instances


def test_flatten_instance_information(sample_instance_data, flattened_instance_data):
    flattened_info = flatten_instance_information(sample_instance_data)
    assert flattened_info == flattened_instance_data


def test_sort_by_price_fn(flattened_instance_data):
    first_element = list(flattened_instance_data.items())[0]
    assert isinstance(sort_by_price_fn(first_element), int)


@mock.patch("pylambdacloud.select_instance.get_offered_instances")
def test_list_instance_types(mock_get_offered_instances, sample_instance_data):
    mock_response = mock.Mock()
    mock_response.json.return_value = {"data": sample_instance_data}
    mock_get_offered_instances.return_value = mock_response

    instances = list_instance_types()
    assert list(instances.keys()) == [
        "gpu_4x_a6000",
        "gpu_1x_a100",
    ]
    assert "gpu_8x_v100" not in instances


@mock.patch("pylambdacloud.select_instance.get_offered_instances")
@mock.patch("pylambdacloud.select_instance.inquirer.list_input")
def test_prompt_for_instance_type(
    mock_list_input, mock_get_offered_instances, sample_instance_data
):
    # Mock the get_offered_instances function to return a mock response
    mock_response = mock.Mock()
    mock_response.json.return_value = {"data": sample_instance_data}
    mock_get_offered_instances.return_value = mock_response

    # Simulate user input
    mock_list_input.side_effect = ["gpu_4x_a6000", "us-phoenix-1"]

    # Call the function under test
    instance_type, region = prompt_for_instance_type()

    # Verify the results
    assert instance_type == "gpu_4x_a6000"
    assert region == "us-phoenix-1"
