"""The drain-order policy: priority first, then FIFO by issue number."""

from growth.queue import channel_of, drain_order


def _item(number, labels=(), title=""):
    return {"number": number, "title": title,
            "labels": [{"name": n} for n in labels]}


def test_fifo_by_number():
    order = drain_order([_item(30), _item(10), _item(20)])
    assert [i["number"] for i in order] == [10, 20, 30]


def test_priority_high_jumps_the_queue():
    order = drain_order([_item(10), _item(30, ["priority:high"]), _item(20)])
    assert [i["number"] for i in order] == [30, 10, 20]


def test_priority_items_stay_fifo_between_themselves():
    order = drain_order([
        _item(40, ["priority:high"]), _item(10), _item(20, ["priority:high"]),
    ])
    assert [i["number"] for i in order] == [20, 40, 10]


def test_items_without_a_number_are_dropped():
    order = drain_order([_item(10), {"title": "no number"}, {"number": True}])
    assert [i["number"] for i in order] == [10]


def test_plain_string_labels_also_work():
    order = drain_order([{"number": 5, "labels": ["priority:high"]}, _item(1)])
    assert [i["number"] for i in order] == [5, 1]


def test_channel_of():
    assert channel_of(_item(1, ["growth-queue", "channel:twitter"])) == "twitter"
    assert channel_of(_item(1, ["growth-queue"])) is None
    assert channel_of(_item(1, ["channel:"])) is None
