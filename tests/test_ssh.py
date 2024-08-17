import pytest
from unittest import mock
from pylambdacloud.ssh import SSHConnection


@pytest.fixture
def instance_info():
    return {
        "instance_id": "i-1234567890abcdef0",
        "host": "example.com",
        "local_ssh_key": "/path/to/private/key",
    }


@pytest.fixture
def ssh_connection(instance_info):
    with mock.patch("pylambdacloud.ssh.Connection", autospec=True):
        with mock.patch(
            "pylambdacloud.ssh.get_terminate_cmd", return_value="terminate command"
        ):
            connection_instance = SSHConnection(instance_info)
            yield connection_instance


def test_init(instance_info):
    with mock.patch("pylambdacloud.ssh.Connection") as mock_connection:
        with mock.patch(
            "pylambdacloud.ssh.get_terminate_cmd", return_value="terminate command"
        ):
            # Instantiate SSHConnection, which should use the mocked Connection
            ssh_connection = SSHConnection(instance_info)

            # Assert that the Connection object was initialized with the correct parameters
            mock_connection.assert_called_once_with(
                instance_info["host"],
                user="ubuntu",
                connect_timeout=600,
                connect_kwargs=(
                    {
                        "key_filename": instance_info["local_ssh_key"],
                        "look_for_keys": False,
                    }
                    if instance_info["local_ssh_key"]
                    else None
                ),
            )

            # Check that terminate_cmd is set correctly
            assert ssh_connection.terminate_cmd == "terminate command"


def test_transfer_files(ssh_connection):
    copy_pairs = [("local_path/file.txt", "remote_path/file.txt")]
    with mock.patch.object(ssh_connection.c, "local") as mock_local:
        ssh_connection.transfer_files(copy_pairs)

        # Build the expected rsync command
        internal_ssh = (
            "ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
        )
        if ssh_connection.local_ssh_key:
            internal_ssh += f" -o IdentitiesOnly=yes -i {ssh_connection.local_ssh_key}"

        expected_command = f'rsync -avz -e "{internal_ssh}" local_path/file.txt {ssh_connection.user}@{ssh_connection.host}:remote_path/file.txt'

        # Assert that the command matches the expected command
        mock_local.assert_called_once_with(expected_command)


def test_construct_command_from_list(ssh_connection):
    commands = ["echo 'Hello World'", "uptime"]
    full_cmd = ssh_connection.construct_command_from_list(commands)
    expected_cmd = (
        f"tmux new-session -d -s {ssh_connection.tmux_session_name};"
        "tmux send-keys -t pylambdacloud 'echo 'Hello World';uptime;terminate command' Enter;"
    )
    assert full_cmd == expected_cmd


def test_run_command_and_terminate(ssh_connection):
    with mock.patch.object(ssh_connection.c, "run") as mock_run:
        with mock.patch.object(ssh_connection.c, "close") as mock_close:
            ssh_connection._run_command_and_terminate("some command")
            mock_run.assert_called_once_with("some command")
            assert ssh_connection.executed_commands == ["some command"]
            mock_close.assert_called_once()


def test_run_commands_and_terminate(ssh_connection):
    commands = ["echo 'Hello World'", "uptime"]
    with mock.patch.object(
        ssh_connection, "construct_command_from_list"
    ) as mock_construct_command:
        with mock.patch.object(
            ssh_connection, "_run_command_and_terminate"
        ) as mock_run_and_terminate:
            ssh_connection.run_commands_and_terminate(commands)
            mock_construct_command.assert_called_once_with(commands)
            mock_run_and_terminate.assert_called_once()
