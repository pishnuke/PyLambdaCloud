import pytest
from unittest import mock
from pylambdacloud.launch_instance import (
    check_instance_and_region_available,
    construct_payload,
    get_instance_info,
    launch_instance,
    is_active,
    terminate_instance,
)


@pytest.fixture
def sample_config():
    return {
        "launch_options": {
            "instance_type_name": "gpu_1x_a100",
            "region_name": "us-tx-1",
            "local_ssh_key": "/path/to/ssh/key",
        }
    }


@pytest.fixture
def sample_launch_response():
    return {"data": {"instance_ids": ["instance-12345"]}}


@pytest.fixture
def sample_instance_response_active():
    return {"data": {"status": "active", "ip": "123.456.78.90"}}


@pytest.fixture
def sample_instance_response_inactive():
    return {"data": {"status": "starting", "ip": None}}


@pytest.fixture
def sample_offered_instances():
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
        }
    }


@mock.patch("pylambdacloud.launch_instance.list_instance_types")
def test_check_instance_and_region_available(mock_list_instance_types):
    mock_list_instance_types.return_value = {
        "gpu_1x_a100": {"regions_with_capacity_available": ["us-tx-1"]}
    }
    assert check_instance_and_region_available("gpu_1x_a100", "us-tx-1") is True
    assert check_instance_and_region_available("gpu_1x_a100", "us-west-2") is False
    assert check_instance_and_region_available("gpu_4x_a6000", "us-tx-1") is False


@mock.patch("pylambdacloud.launch_instance.prompt_for_instance_type")
@mock.patch("pylambdacloud.launch_instance.list_instance_types")
def test_construct_payload(
    mock_list_instance_types, mock_prompt_for_instance_type, sample_config
):
    mock_list_instance_types.return_value = {
        "gpu_1x_a100": {"regions_with_capacity_available": ["us-tx-1"]}
    }
    mock_prompt_for_instance_type.return_value = ("gpu_1x_a100", "us-tx-1")

    payload = construct_payload(sample_config["launch_options"])
    assert payload["instance_type_name"] == "gpu_1x_a100"
    assert payload["region_name"] == "us-tx-1"

    # Simulate unavailability and prompt for new selection
    mock_list_instance_types.return_value = {
        "gpu_4x_a6000": {"regions_with_capacity_available": ["us-west-2"]}
    }
    mock_prompt_for_instance_type.return_value = ("gpu_4x_a6000", "us-west-2")
    sample_config["launch_options"]["instance_type_name"] = "gpu_4x_a6000"
    sample_config["launch_options"]["region_name"] = "us-west-2"

    payload = construct_payload(sample_config["launch_options"])
    assert payload["instance_type_name"] == "gpu_4x_a6000"
    assert payload["region_name"] == "us-west-2"


@mock.patch("pylambdacloud.launch_instance.get_instance")
def test_is_active(
    mock_get_instance,
    sample_instance_response_active,
    sample_instance_response_inactive,
):
    mock_get_instance.return_value.json.return_value = sample_instance_response_active
    assert is_active("instance-12345") is True

    mock_get_instance.return_value.json.return_value = sample_instance_response_inactive
    assert is_active("instance-12345") is False


@mock.patch("pylambdacloud.launch_instance.get_instance")
@mock.patch("time.sleep", return_value=None)  # Mock sleep to avoid delays
def test_get_instance_info(
    mock_time_sleep,
    mock_get_instance,
    sample_launch_response,
    sample_instance_response_active,
    sample_instance_response_inactive,
):
    # Provide several inactive responses followed by an active response
    mock_get_instance.side_effect = [
        mock.Mock(
            json=mock.Mock(return_value=sample_instance_response_inactive)
        ),  # 1st check: inactive
        mock.Mock(
            json=mock.Mock(return_value=sample_instance_response_inactive)
        ),  # 2nd check: inactive
        mock.Mock(
            json=mock.Mock(return_value=sample_instance_response_active)
        ),  # 3rd check: active
    ]

    print(mock_get_instance().json())
    print(mock_get_instance().json())

    response_mock = mock.Mock()
    response_mock.json.return_value = sample_launch_response

    # Call the function under test
    instance_info = get_instance_info(response_mock)

    # Verify that the instance info is correct
    assert instance_info["instance_id"] == "instance-12345"
    assert instance_info["host"] == "123.456.78.90"

    # Verify that get_instance was called the expected number of times
    assert mock_get_instance.call_count == 3


@mock.patch("pylambdacloud.select_instance.get_offered_instances")
@mock.patch("pylambdacloud.launch_instance.get_instance_info")
@mock.patch("pylambdacloud.launch_instance.launch_instance_call")
def test_launch_instance(
    mock_launch_instance_call,
    mock_get_instance_info,
    mock_get_offered_instances,
    sample_config,
    sample_launch_response,
    sample_offered_instances,
):
    # Mock the get_offered_instances to return the sample_offered_instances
    mock_get_offered_instances.return_value.json.return_value = {
        "data": sample_offered_instances
    }

    # Mock the launch_instance_call to return a controlled launch response
    mock_launch_instance_call.return_value = mock.Mock(
        json=mock.Mock(return_value=sample_launch_response)
    )

    # Mock the get_instance_info to return the active instance information
    get_instance_info_return_values = {
        "instance_id": "instance-12345",
        "host": "123.456.78.90",
        "local_ssh_key": "/path/to/ssh/key",
    }
    mock_get_instance_info.return_value = get_instance_info_return_values

    # Call the function under test
    instance_info = launch_instance(sample_config)

    # Verify that the instance info is correct
    assert (
        instance_info["instance_id"] == get_instance_info_return_values["instance_id"]
    )
    assert instance_info["host"] == get_instance_info_return_values["host"]
    assert (
        instance_info["local_ssh_key"]
        == get_instance_info_return_values["local_ssh_key"]
    )

    # Ensure the API was called with the correct payload
    mock_launch_instance_call.assert_called_once_with(sample_config["launch_options"])


@mock.patch("pylambdacloud.launch_instance.terminate_instance_call")
def test_terminate_instance(mock_terminate_instance_call):
    mock_response = mock.Mock()
    mock_terminate_instance_call.return_value = mock_response

    response = terminate_instance("instance-12345")
    assert response == mock_response
    mock_terminate_instance_call.assert_called_once_with(
        {"instance_ids": ["instance-12345"]}
    )
