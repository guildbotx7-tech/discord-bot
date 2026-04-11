"""Tests for clan monitoring Discord commands."""

import pytest


def test_clan_monitoring_commands_exist():
    """Verify command functions exist."""
    from cogs.clan_monitoring_commands import ClanMonitoringCog

    cog = ClanMonitoringCog(None)

    assert hasattr(cog, "show_clan_changes")
    assert hasattr(cog, "show_recent_joins")
    assert hasattr(cog, "show_recent_leaves")
    assert hasattr(cog, "show_clan_stats")


def test_clan_monitoring_commands_are_callable():
    """Verify command methods are callable."""
    from cogs.clan_monitoring_commands import ClanMonitoringCog

    cog = ClanMonitoringCog(None)

    assert callable(cog.show_clan_changes)
    assert callable(cog.show_recent_joins)
    assert callable(cog.show_recent_leaves)
    assert callable(cog.show_clan_stats)
