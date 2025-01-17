from mock import MagicMock, patch

from shared.analytics_tracking import (
    BLANK_SEGMENT_USER_ID,
    on_error,
    setup_analytics,
    track_betaprofiling_added_in_YAML,
    track_betaprofiling_removed_from_YAML,
    track_critical_files_sent,
    track_event,
    track_manual_critical_file_labelling_added_in_YAML,
    track_manual_critical_file_labelling_removed_from_YAML,
    track_related_entrypoints_sent,
    track_show_critical_paths_added_in_YAML,
    track_show_critical_paths_removed_from_YAML,
    track_user,
)
from tests.base import BaseTestCase


class TestAnalyticsTracking(BaseTestCase):
    def test_track_event(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.analytics.track")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)

        track_event(
            "123",
            "Coverage Report Passed",
            is_enterprise=False,
            event_data={"test": True},
        )
        assert mock_track.called

    def test_track_event_invalid_name(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.analytics.track")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)

        track_event(
            "123", "Invalid Name", is_enterprise=False, event_data={"test": True}
        )
        assert not mock_track.called

    def test_track_event_segment_disabled(self, mocker):
        mocker.patch("shared.analytics_tracking.segment_enabled", False)
        mock_track = mocker.patch("shared.analytics_tracking.analytics.track")

        track_event(
            "123",
            "Coverage Report Failed",
            is_enterprise=False,
            event_data={"test": True},
        )
        assert not mock_track.called

    def test_track_event_is_enterprise(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.analytics.track")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)

        track_event(
            "123",
            "Coverage Report Failed",
            is_enterprise=True,
            event_data={"test": True},
        )
        assert not mock_track.called

    def test_track_user(self, mocker):
        mock_identify = mocker.patch("shared.analytics_tracking.analytics.identify")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)

        track_user("456", {"username": "test"})
        assert mock_identify.called

    def test_track_user_segment_disabled(self, mocker):
        mock_identify = mocker.patch("shared.analytics_tracking.analytics.identify")
        mocker.patch("shared.analytics_tracking.segment_enabled", False)

        track_user("456", {"username": "test"})
        assert not mock_identify.called

    @patch("shared.analytics_tracking.analytics.identify")
    def test_track_user_is_enterprise(self, mocker):
        mock_identify = mocker.patch("shared.analytics_tracking.analytics.identify")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)

        track_user("456", {"username": "test"}, True)
        assert not mock_identify.called

    def test_on_error(self):
        on_error("Not initialized with API key")

    def test_setup_analytics(self, mock_configuration):
        mock_configuration.set_params(
            {"setup": {"debug": True, "segment": {"key": "123"}}}
        )
        setup_analytics()

    def test_track_critical_files_sent(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_critical_files_sent(
            repoid="123",
            ownerid="abc",
            commitid="abc123",
            pullid="7",
            is_enterprise=False,
        )
        assert mock_track.called

    def test_track_related_entrypoints_sent(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_related_entrypoints_sent(
            repoid="123",
            ownerid="abc",
            commitid="abc123",
            pullid="7",
            is_enterprise=False,
        )

    def test_track_betaprofiling_added_in_YAML(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_betaprofiling_added_in_YAML(
            repoid="123", ownerid="456", is_enterprise=False
        )
        assert mock_track.called

    def test_track_betaprofiling_removed_from_YAML(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_betaprofiling_removed_from_YAML(
            repoid="123", ownerid="456", is_enterprise=False
        )
        assert mock_track.called

    def test_track_show_critical_paths_added_in_YAML(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_show_critical_paths_added_in_YAML(
            repoid="123", ownerid="456", is_enterprise=False
        )
        assert mock_track.called

    def test_track_show_critical_paths_removed_from_YAML(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_show_critical_paths_removed_from_YAML(
            repoid="123", ownerid="456", is_enterprise=False
        )
        assert mock_track.called

    def test_track_manual_critical_file_labelling_added_in_YAML(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_manual_critical_file_labelling_added_in_YAML(
            repoid="123", ownerid="456", is_enterprise=False
        )
        mock_track.assert_called_with(
            user_id=BLANK_SEGMENT_USER_ID,
            event_name="Impact Analysis Manual Critical File Labelling in YAML",
            event_data={"repo_id": "123", "repo_owner_id": "456"},
            is_enterprise=False,
        )

    def test_track_manual_critical_file_labelling_removed_from_YAML(self, mocker):
        mock_track = mocker.patch("shared.analytics_tracking.track_event")
        mocker.patch("shared.analytics_tracking.segment_enabled", True)
        track_manual_critical_file_labelling_removed_from_YAML(
            repoid="123", ownerid="456", is_enterprise=False
        )
        mock_track.assert_called_with(
            user_id=BLANK_SEGMENT_USER_ID,
            event_name="Impact Analysis Manual Critical File Labelling removed from YAML",
            event_data={"repo_id": "123", "repo_owner_id": "456"},
            is_enterprise=False,
        )
