from governance.metadata_sync import AssetMetadata, StaticMetadataSource, sync_metadata
from governance.service import GovernanceService


def test_sync_upserts_assets(db):
    source = StaticMetadataSource([
        AssetMetadata("orders", "snowflake", owner="data-team", classification="internal"),
        AssetMetadata("events", "kafka", owner=None, classification=None),
    ])
    summary = sync_metadata(db, source)
    assert summary.upserted == 2

    assets = {a.name: a for a in GovernanceService(db).list_assets()}
    assert assets["orders"].owner == "data-team"
    assert assets["orders"].is_complete
    assert not assets["events"].is_complete


def test_sync_marks_absent_assets_stale(db):
    sync_metadata(db, StaticMetadataSource([
        AssetMetadata("a", "snowflake"),
        AssetMetadata("b", "snowflake"),
    ]))
    summary = sync_metadata(db, StaticMetadataSource([
        AssetMetadata("a", "snowflake"),  # b disappeared
    ]))
    assert summary.marked_stale == 1

    assets = {a.name: a for a in GovernanceService(db).list_assets()}
    assert assets["b"].stale is True
    assert assets["a"].stale is False


def test_sync_refreshes_owner_and_clears_stale(db):
    sync_metadata(db, StaticMetadataSource([AssetMetadata("a", "snowflake")]))
    sync_metadata(db, StaticMetadataSource([]))  # a becomes stale
    assert GovernanceService(db).list_assets()[0].stale is True

    # a reappears with ownership metadata -> no longer stale, now complete
    sync_metadata(db, StaticMetadataSource([
        AssetMetadata("a", "snowflake", owner="o", classification="internal"),
    ]))
    asset = GovernanceService(db).list_assets()[0]
    assert asset.stale is False
    assert asset.is_complete
