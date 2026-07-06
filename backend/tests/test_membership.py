from pchome.core.membership import GroupMembership


class TestInit:
    def test_dedupes_preserving_order(self):
        m = GroupMembership(["A", "B", "A", "C"])
        assert m.active_ids() == ["A", "B", "C"]

    def test_defaults_to_empty(self):
        m = GroupMembership()
        assert m.active_ids() == []
        assert m.empty()


class TestAddRemove:
    def test_add_appends_new_member(self):
        m = GroupMembership(["A"])
        assert m.add("B") is True
        assert m.active_ids() == ["A", "B"]

    def test_add_duplicate_is_noop_but_returns_true(self):
        m = GroupMembership(["A"])
        assert m.add("A") is True
        assert m.active_ids() == ["A"]

    def test_remove_drops_member(self):
        m = GroupMembership(["A", "B"])
        m.remove("A")
        assert m.active_ids() == ["B"]

    def test_remove_nonexistent_is_noop(self):
        m = GroupMembership(["A"])
        m.remove("Z")
        assert m.active_ids() == ["A"]

    def test_empty_true_only_when_no_members(self):
        m = GroupMembership(["A"])
        assert not m.empty()
        m.remove("A")
        assert m.empty()


class TestFreeze:
    def test_freeze_returns_final_list(self):
        m = GroupMembership(["A", "B"])
        assert m.freeze() == ["A", "B"]

    def test_add_after_freeze_fails_and_does_not_mutate(self):
        m = GroupMembership(["A"])
        m.freeze()
        assert m.add("B") is False
        assert m.active_ids() == ["A"]

    def test_remove_after_freeze_still_allowed(self):
        # 目前實作 remove() 不檢查 _frozen；本測試記錄現況行為
        m = GroupMembership(["A", "B"])
        m.freeze()
        m.remove("A")
        assert m.active_ids() == ["B"]
